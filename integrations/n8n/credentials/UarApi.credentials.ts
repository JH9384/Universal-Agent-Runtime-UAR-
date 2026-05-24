import {
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class UarApi implements ICredentialType {
	name = 'uarApi';
	displayName = 'UAR API';
	documentationUrl = 'https://docs.universalagent.io';

	properties: INodeProperties[] = [
		{
			displayName: 'Server URL',
			name: 'server',
			type: 'string',
			default: 'https://api.universalagent.io',
			required: true,
		},
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
		},
	];
}
