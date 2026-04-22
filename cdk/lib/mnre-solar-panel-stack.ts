import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions';
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import * as path from 'path';

export class MnreSolarPanelStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

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

    // ─── DynamoDB Tables ───
    const submissionsTable = new dynamodb.Table(this, 'SubmissionsTable', {
      partitionKey: { name: 'submissionId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    submissionsTable.addGlobalSecondaryIndex({
      indexName: 'userId-index',
      partitionKey: { name: 'userId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'uploadedAt', type: dynamodb.AttributeType.STRING },
    });

    const embeddingsTable = new dynamodb.Table(this, 'EmbeddingsTable', {
      partitionKey: { name: 'imageId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ─── Lambda Layer (common utilities) ───
    const commonLayer = new lambda.LayerVersion(this, 'CommonLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/layers/common')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Common utilities for MNRE lambdas',
    });

    const lambdaDefaults = {
      runtime: lambda.Runtime.PYTHON_3_12,
      layers: [commonLayer],
      timeout: cdk.Duration.seconds(120),
      memorySize: 512,
    };

    // ─── Lambda: Upload ───
    const uploadFn = new lambda.Function(this, 'UploadFunction', {
      ...lambdaDefaults,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/upload')),
      handler: 'handler.lambda_handler',
      environment: {
        BUCKET_NAME: imageBucket.bucketName,
        SUBMISSIONS_TABLE: submissionsTable.tableName,
      },
    });
    imageBucket.grantPut(uploadFn);
    imageBucket.grantRead(uploadFn);
    submissionsTable.grantWriteData(uploadFn);

    // ─── Lambda: Confirm Upload (starts Step Function after S3 upload) ───
    const confirmUploadFn = new lambda.Function(this, 'ConfirmUploadFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/confirm_upload')),
      handler: 'handler.lambda_handler',
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
        STATE_MACHINE_ARN: '', // set after state machine creation
      },
    });
    imageBucket.grantRead(confirmUploadFn);
    submissionsTable.grantReadData(confirmUploadFn);

    // ─── Lambda: Quality Check ───
    const qualityCheckFn = new lambda.Function(this, 'QualityCheckFunction', {
      ...lambdaDefaults,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/quality_check')),
      handler: 'handler.lambda_handler',
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
      },
    });
    imageBucket.grantRead(qualityCheckFn);
    imageBucket.grantPut(qualityCheckFn);
    submissionsTable.grantWriteData(qualityCheckFn);
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
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
        EMBEDDINGS_TABLE: embeddingsTable.tableName,
        BUCKET_NAME: imageBucket.bucketName,
      },
    });
    imageBucket.grantRead(duplicationCheckFn);
    submissionsTable.grantWriteData(duplicationCheckFn);
    embeddingsTable.grantReadData(duplicationCheckFn);
    duplicationCheckFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: ['arn:aws:bedrock:*::foundation-model/amazon.titan-embed-image-v1'],
    }));

    // ─── Lambda: Custom Checks (Gemma 3 12B IT via Bedrock) ───
    const customChecksFn = new lambda.Function(this, 'CustomChecksFunction', {
      ...lambdaDefaults,
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/custom_checks')),
      handler: 'handler.lambda_handler',
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
        BUCKET_NAME: imageBucket.bucketName,
      },
    });
    imageBucket.grantRead(customChecksFn);
    submissionsTable.grantWriteData(customChecksFn);
    customChecksFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:Converse'],
      resources: [
        'arn:aws:bedrock:*::foundation-model/google.gemma-3-12b-it',
      ],
    }));

    // ─── Lambda: Store Result ───
    const storeResultFn = new lambda.Function(this, 'StoreResultFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/store_result')),
      handler: 'handler.lambda_handler',
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
      },
    });
    submissionsTable.grantWriteData(storeResultFn);

    // ─── Lambda: Index Image ───
    const indexImageFn = new lambda.Function(this, 'IndexImageFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/index_image')),
      handler: 'handler.lambda_handler',
      environment: {
        EMBEDDINGS_TABLE: embeddingsTable.tableName,
      },
    });
    embeddingsTable.grantWriteData(indexImageFn);

    // ─── Lambda: Get Status ───
    const getStatusFn = new lambda.Function(this, 'GetStatusFunction', {
      ...lambdaDefaults,
      timeout: cdk.Duration.seconds(30),
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambdas/get_status')),
      handler: 'handler.lambda_handler',
      environment: {
        SUBMISSIONS_TABLE: submissionsTable.tableName,
      },
    });
    submissionsTable.grantReadWriteData(getStatusFn);

    // ─── Step Functions State Machine ───
    const waitForUpload = new sfn.Wait(this, 'WaitForUpload', {
      time: sfn.WaitTime.duration(cdk.Duration.seconds(10)),
    });

    // Error handler: store failure to DynamoDB so frontend sees it immediately
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

    const customChecksTask = new tasks.LambdaInvoke(this, 'CustomChecksTask', {
      lambdaFunction: customChecksFn,
      outputPath: '$.Payload',
    });
    customChecksTask.addCatch(storeErrorResult, { resultPath: '$.error-info' });

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

    const rejectCustom = new sfn.Pass(this, 'RejectCustom', {
      result: sfn.Result.fromObject({ status: 'REJECTED', reason: 'custom_check_failed' }),
      resultPath: '$.finalDecision',
    });

    const acceptSubmission = new sfn.Pass(this, 'AcceptSubmission', {
      result: sfn.Result.fromObject({ status: 'ACCEPTED', reason: 'all_checks_passed' }),
      resultPath: '$.finalDecision',
    });

    // Store result for rejection paths
    const storeRejectQuality = new tasks.LambdaInvoke(this, 'StoreRejectQuality', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });
    const storeRejectDuplicate = new tasks.LambdaInvoke(this, 'StoreRejectDuplicate', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });
    const storeRejectCustom = new tasks.LambdaInvoke(this, 'StoreRejectCustom', {
      lambdaFunction: storeResultFn,
      outputPath: '$.Payload',
    });

    const isQualityPassed = new sfn.Choice(this, 'IsQualityPassed')
      .when(sfn.Condition.booleanEquals('$.qualityCheckResult.passed', true), duplicationCheckTask)
      .otherwise(rejectQuality.next(storeRejectQuality));

    const isDuplicationPassed = new sfn.Choice(this, 'IsDuplicationPassed')
      .when(sfn.Condition.booleanEquals('$.duplicationCheckResult.passed', true), customChecksTask)
      .otherwise(rejectDuplicate.next(storeRejectDuplicate));

    const isCustomPassed = new sfn.Choice(this, 'IsCustomPassed')
      .when(sfn.Condition.booleanEquals('$.customCheckResult.passed', true), indexImageTask)
      .otherwise(rejectCustom.next(storeRejectCustom));

    qualityCheckTask.next(isQualityPassed);
    duplicationCheckTask.next(isDuplicationPassed);
    customChecksTask.next(isCustomPassed);
    indexImageTask.next(acceptSubmission).next(storeResultTask);

    const definition = waitForUpload.next(qualityCheckTask);

    const stateMachine = new sfn.StateMachine(this, 'VerificationStateMachine', {
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      timeout: cdk.Duration.minutes(10),
    });

    // Grant confirm function permission to start the state machine
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

    // ─── Frontend Hosting ───
    const frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    const distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(frontendBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      defaultRootObject: 'index.html',
      errorResponses: [
        { httpStatus: 403, responseHttpStatus: 200, responsePagePath: '/index.html' },
        { httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html' },
      ],
    });

    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../frontend/dist'))],
      destinationBucket: frontendBucket,
      distribution,
      distributionPaths: ['/*'],
    });

    // ─── Outputs ───
    new cdk.CfnOutput(this, 'ApiUrl', { value: api.url });
    new cdk.CfnOutput(this, 'CloudFrontUrl', { value: `https://${distribution.distributionDomainName}` });
    new cdk.CfnOutput(this, 'ImageBucketName', { value: imageBucket.bucketName });
    new cdk.CfnOutput(this, 'SubmissionsTableName', { value: submissionsTable.tableName });
    new cdk.CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
  }
}
