#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { MnreSolarPanelStack } from '../lib/mnre-solar-panel-stack';

const app = new cdk.App();
new MnreSolarPanelStack(app, 'MnreSolarPanelPocStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: 'ap-south-1',
  },
});
app.synth();
