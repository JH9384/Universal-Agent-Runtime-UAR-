import {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	NodeOperationError,
} from 'n8n-workflow';

export class Uar implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'UAR',
		name: 'uar',
		icon: 'file:uar.svg',
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description: 'Execute UAR skills and recipes',
		defaults: {
			name: 'UAR',
		},
		inputs: ['main'],
		outputs: ['main'],
		credentials: [
			{
				name: 'uarApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Run Goal',
						value: 'runGoal',
						action: 'Run a UAR goal',
					},
					{
						name: 'Run Recipe',
						value: 'runRecipe',
						action: 'Run a UAR recipe',
					},
					{
						name: 'Call Skill',
						value: 'callSkill',
						action: 'Call a single skill',
					},
				],
				default: 'runGoal',
			},
			{
				displayName: 'Goal',
				name: 'goal',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: {
						operation: ['runGoal', 'runRecipe'],
					},
				},
			},
			{
				displayName: 'Recipe ID',
				name: 'recipeId',
				type: 'string',
				default: 'review',
				required: true,
				displayOptions: {
					show: {
						operation: ['runRecipe'],
					},
				},
			},
			{
				displayName: 'Skill Name',
				name: 'skillName',
				type: 'string',
				default: 'doc_ingest',
				required: true,
				displayOptions: {
					show: {
						operation: ['callSkill'],
					},
				},
			},
			{
				displayName: 'Skills',
				name: 'skills',
				type: 'string',
				default: 'doc_ingest,ollama_generate',
				placeholder: 'comma,separated,skills',
				displayOptions: {
					show: {
						operation: ['runGoal'],
					},
				},
			},
			{
				displayName: 'Input Path',
				name: 'inputPath',
				type: 'string',
				default: '',
				placeholder: '/path/to/file_or_dir',
			},
			{
				displayName: 'Metadata (JSON)',
				name: 'metadata',
				type: 'json',
				default: '{}',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];

		const credentials = await this.getCredentials('uarApi');
		const server = (credentials.server as string) || 'https://api.universalagent.io';
		const apiKey = credentials.apiKey as string;

		for (let i = 0; i < items.length; i++) {
			const operation = this.getNodeParameter('operation', i) as string;
			const goal = this.getNodeParameter('goal', i, '') as string;
			const recipeId = this.getNodeParameter('recipeId', i, '') as string;
			const skillName = this.getNodeParameter('skillName', i, '') as string;
			const skillsStr = this.getNodeParameter('skills', i, '') as string;
			const inputPath = this.getNodeParameter('inputPath', i, '') as string;
			const metadataStr = this.getNodeParameter('metadata', i, '{}') as string;

			let payload: Record<string, unknown> = {};

			if (operation === 'runGoal') {
				payload = {
					goal,
					skills: skillsStr.split(',').map((s) => s.trim()).filter(Boolean),
					metadata: JSON.parse(metadataStr),
				};
				if (inputPath) {
					payload.metadata = { ...(payload.metadata as object), input_path: inputPath };
				}
			} else if (operation === 'runRecipe') {
				payload = {
					goal,
					recipe_id: recipeId,
					metadata: JSON.parse(metadataStr),
				};
			} else if (operation === 'callSkill') {
				payload = {
					goal: `Run skill ${skillName}`,
					skills: [skillName],
					metadata: JSON.parse(metadataStr),
				};
			}

			const response = await this.helpers.request({
				method: 'POST',
				uri: `${server}/api/uar/run`,
				body: payload,
				json: true,
				headers: {
					Authorization: `Bearer ${apiKey}`,
				},
			});

			if (response.error) {
				throw new NodeOperationError(this.getNode(), response.error);
			}

			returnData.push({
				json: response,
			});
		}

		return [returnData];
	}
}
