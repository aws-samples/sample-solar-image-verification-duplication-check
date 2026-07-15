import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as amplify from 'aws-cdk-lib/aws-amplify';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import { Construct } from 'constructs';
import * as path from 'path';

export class MnreSolarPanelStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Instance size is overridable so customers can pick their own class:
    //   cdk deploy -c dbInstanceClass=t3.small
    // Instance type is overridable so customers can pick their own class:
    //   cdk deploy -c dbInstanceType=t3.small   (default: t3.micro)
    const dbInstanceTypeStr = (this.node.tryGetContext('dbInstanceType') as string) || 't3.micro';
    const dbMultiAz = (this.node.tryGetContext('dbMultiAz') as string) === 'true';

    // ─── VPC (private-isolated subnets only, no NAT) ───
    const vpc = new ec2.Vpc(this, 'AppVpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [
        { name: 'private', subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 },
      ],
    });

    // Gateway endpoint for S3 (free, no ENI)
    vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });

    // Interface endpoints so VPC-attached Lambdas can reach AWS APIs without NAT
    const interfaceEndpoints: Record<string, ec2.InterfaceVpcEndpointAwsService> = {
      Rekognition: ec2.InterfaceVpcEndpointAwsService.REKOGNITION,
      Bedrock: ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
      SecretsManager: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
      StepFunctions: ec2.InterfaceVpcEndpointAwsService.STEP_FUNCTIONS,
      CloudWatchLogs: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
    };
    for (const [name, service] of Object.entries(interfaceEndpoints)) {
      vpc.addInterfaceEndpoint(`${name}Endpoint`, { service });
    }

    // ─── S3 Bucket for uploaded images ───
    const imageBucket = new s3.Bucket(this, 'ImageBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      cors: [
        {
          allowedHeaders: ['*'],
          allowedMethods: [s3.HttpMethods.PUT, s3.HttpMethods.GET],
          allowedOrigins: ['*'],
          maxAge: 3600,
        },
      ],
    });

    // ─── RDS PostgreSQL (pgvector) ───
    const dbSecurityGroup = new ec2.SecurityGroup(this, 'DbSecurityGroup', {
      vpc,
      description: 'Allow PostgreSQL from Lambdas',
      allowAllOutbound: true,
    });

    const lambdaSecurityGroup = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
      vpc,
      description: 'Lambda functions',
      allowAllOutbound: true,
    });

    dbSecurityGroup.addIngressRule(
      lambdaSecurityGroup,
      ec2.Port.tcp(5432),
      'PostgreSQL from Lambda',
    );

    const database = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({ version: rds.PostgresEngineVersion.VER_16_9 }),
      instanceType: new ec2.InstanceType(dbInstanceTypeStr),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [dbSecurityGroup],
      multiAz: dbMultiAz,
      allocatedStorage: 20,
      databaseName: 'solar',
      credentials: rds.Credentials.fromGeneratedSecret('solaradmin'),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      deleteAutomatedBackups: true,
      backupRetention: cdk.Duration.days(0),
    });

    const dbSecret = database.secret!;

    // Shared DB environment for every data-touching Lambda
    const dbEnv = {
      DB_HOST: database.dbInstanceEndpointAddress,
      DB_PORT: database.dbInstanceEndpointPort,
      DB_NAME: 'solar',
      DB_SECRET_ARN: dbSecret.secretArn,
    };

    // ─── Lambda Layer (common utilities + psycopg) ───
    const commonLayer = new lambda.LayerVersion(this, 'CommonLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/layers/common')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Common utilities + psycopg for MNRE lambdas',
    });

    const lambdaDefaults = {
      runtime: lambda.Runtime.PYTHON_3_12,
      layers: [commonLayer],
      timeout: cdk.Duration.seconds(120),
      memorySize: 512,
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [lambdaSecurityGroup],
    };

    // ─── Lambda: Upload ───
    const uploadFn = new lambda.Function(this, 'UploadFunction', {
      ...lambdaDefaults,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/upload')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv, BUCKET_NAME: imageBucket.bucketName },
    });
    imageBucket.grantPut(uploadFn);
    imageBucket.grantRead(uploadFn);
    dbSecret.grantRead(uploadFn);

    // ─── Lambda: Confirm Upload (starts Step Function after S3 upload) ───
    const confirmUploadFn = new lambda.Function(this, 'ConfirmUploadFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/confirm_upload')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv, STATE_MACHINE_ARN: '' },
    });
    imageBucket.grantRead(confirmUploadFn);
    dbSecret.grantRead(confirmUploadFn);

    // ─── Lambda: Quality Check ───
    const qualityCheckFn = new lambda.Function(this, 'QualityCheckFunction', {
      ...lambdaDefaults,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/quality_check')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv },
    });
    imageBucket.grantRead(qualityCheckFn);
    imageBucket.grantPut(qualityCheckFn);
    dbSecret.grantRead(qualityCheckFn);
    qualityCheckFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['rekognition:DetectLabels', 'rekognition:DetectModerationLabels'],
      resources: ['*'],
    }));

    // ─── Lambda: Duplication Check ───
    const duplicationCheckFn = new lambda.Function(this, 'DuplicationCheckFunction', {
      ...lambdaDefaults,
      memorySize: 1024,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/duplication_check')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv, BUCKET_NAME: imageBucket.bucketName },
    });
    imageBucket.grantRead(duplicationCheckFn);
    dbSecret.grantRead(duplicationCheckFn);
    duplicationCheckFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: ['arn:aws:bedrock:*::foundation-model/amazon.titan-embed-image-v1'],
    }));

    // ─── Lambda: Store Result ───
    const storeResultFn = new lambda.Function(this, 'StoreResultFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/store_result')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv },
    });
    dbSecret.grantRead(storeResultFn);

    // ─── Lambda: Index Image ───
    const indexImageFn = new lambda.Function(this, 'IndexImageFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/index_image')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv },
    });
    dbSecret.grantRead(indexImageFn);

    // ─── Lambda: Get Status ───
    const getStatusFn = new lambda.Function(this, 'GetStatusFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/get_status')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv },
    });
    dbSecret.grantRead(getStatusFn);

    // ─── Lambda: DB Init (custom resource — creates extension, tables, index) ───
    const dbInitFn = new lambda.Function(this, 'DbInitFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(120),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/db_init')),
      handler: 'handler.lambda_handler',
      environment: { ...dbEnv },
    });
    dbSecret.grantRead(dbInitFn);

    const dbInitProvider = new cr.Provider(this, 'DbInitProvider', {
      onEventHandler: dbInitFn,
    });
    const dbInitResource = new cdk.CustomResource(this, 'DbInitResource', {
      serviceToken: dbInitProvider.serviceToken,
    });
    dbInitResource.node.addDependency(database);

    // ─── Step Functions State Machine ───
    const waitForUpload = new sfn.Wait(this, 'WaitForUpload', {
      time: sfn.WaitTime.duration(cdk.Duration.seconds(10)),
    });

    const storeErrorResult = new tasks.LambdaInvoke(this, 'StoreErrorResult', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });

    const qualityCheckTask = new tasks.LambdaInvoke(this, 'QualityCheckTask', {
      lambdaFunction: qualityCheckFn,
      outputPath: '$.Payload',
    });
    qualityCheckTask.addCatch(storeErrorResult, { resultPath: '$.error-info' });

    const duplicationCheckTask = new tasks.LambdaInvoke(this, 'DuplicationCheckTask', {
      lambdaFunction: duplicationCheckFn,
      outputPath: '$.Payload',
    });
    duplicationCheckTask.addCatch(storeErrorResult, { resultPath: '$.error-info' });

    const indexImageTask = new tasks.LambdaInvoke(this, 'IndexImageTask', {
      lambdaFunction: indexImageFn,
      outputPath: '$.Payload',
    });
    indexImageTask.addCatch(storeErrorResult, { resultPath: '$.error-info' });

    const storeResultTask = new tasks.LambdaInvoke(this, 'StoreResultTask', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });

    const rejectQuality = new sfn.Pass(this, 'RejectQuality', {
      result: sfn.Result.fromObject({ status: 'REJECTED', reason: 'quality_check_failed' }),
      resultPath: '$.finalDecision',
    });

    const rejectDuplicate = new sfn.Pass(this, 'RejectDuplicate', {
      result: sfn.Result.fromObject({ status: 'REJECTED', reason: 'duplicate_image' }),
      resultPath: '$.finalDecision',
    });

    const acceptSubmission = new sfn.Pass(this, 'AcceptSubmission', {
      result: sfn.Result.fromObject({ status: 'ACCEPTED', reason: 'all_checks_passed' }),
      resultPath: '$.finalDecision',
    });

    const storeRejectQuality = new tasks.LambdaInvoke(this, 'StoreRejectQuality', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });
    const storeRejectDuplicate = new tasks.LambdaInvoke(this, 'StoreRejectDuplicate', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });

    const isQualityPassed = new sfn.Choice(this, 'IsQualityPassed')
      .when(sfn.Condition.booleanEquals('$.qualityCheckResult.passed', true), duplicationCheckTask)
      .otherwise(rejectQuality.next(storeRejectQuality));

    const isDuplicationPassed = new sfn.Choice(this, 'IsDuplicationPassed')
      .when(sfn.Condition.booleanEquals('$.duplicationCheckResult.passed', true), indexImageTask)
      .otherwise(rejectDuplicate.next(storeRejectDuplicate));

    qualityCheckTask.next(isQualityPassed);
    duplicationCheckTask.next(isDuplicationPassed);
    indexImageTask.next(acceptSubmission).next(storeResultTask);

    const definition = waitForUpload.next(qualityCheckTask);

    const stateMachine = new sfn.StateMachine(this, 'VerificationStateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(10),
    });

    stateMachine.grantStartExecution(confirmUploadFn);
    confirmUploadFn.addEnvironment('STATE_MACHINE_ARN', stateMachine.stateMachineArn);

    // ─── API Gateway ───
    const api = new apigateway.RestApi(this, 'MnreApi', {
      restApiName: 'MNRE Solar Panel API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    const uploadResource = api.root.addResource('upload');
    uploadResource.addMethod('POST', new apigateway.LambdaIntegration(uploadFn));

    const confirmResource = api.root.addResource('confirm');
    confirmResource.addMethod('POST', new apigateway.LambdaIntegration(confirmUploadFn));

    const statusResource = api.root.addResource('status');
    const submissionIdResource = statusResource.addResource('{submissionId}');
    submissionIdResource.addMethod('GET', new apigateway.LambdaIntegration(getStatusFn));

    const submissionsResource = api.root.addResource('submissions');
    submissionsResource.addMethod('GET', new apigateway.LambdaIntegration(getStatusFn));

    // ─── Frontend Hosting (AWS Amplify — regional app resource in ap-south-1) ───
    // Manual-deploy Amplify app: deploy.py zips frontend/dist and pushes it via
    // `aws amplify start-deployment`, keeping the app resource in the stack region.
    const amplifyApp = new amplify.CfnApp(this, 'FrontendApp', {
      name: 'solar-portal-frontend',
      description: 'MNRE Solar Panel Verification Portal frontend',
      customRules: [
        // SPA fallback: route all paths to index.html
        { source: '</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>', target: '/index.html', status: '200' },
      ],
    });

    const amplifyBranch = new amplify.CfnBranch(this, 'FrontendBranch', {
      appId: amplifyApp.attrAppId,
      branchName: 'main',
      description: 'Production branch (manual deployments)',
    });

    // ─── Outputs ───
    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url });
    new cdk.CfnOutput(this, 'AmplifyAppId', { value: amplifyApp.attrAppId });
    new cdk.CfnOutput(this, 'FrontendUrl', { value: `https://main.${amplifyApp.attrDefaultDomain}` });
    new cdk.CfnOutput(this, 'ImageBucketName', { value: imageBucket.bucketName });
    new cdk.CfnOutput(this, 'DbEndpoint', { value: database.dbInstanceEndpointAddress });
    new cdk.CfnOutput(this, 'DbSecretArn', { value: dbSecret.secretArn });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
  }
}
