export const manifest = (() => {
function __memo(fn) {
	let value;
	return () => value ??= (value = fn());
}

return {
	appDir: "_app",
	appPath: "_app",
	assets: new Set([]),
	mimeTypes: {},
	_: {
		client: {start:"_app/immutable/entry/start.DsbP8iJ8.js",app:"_app/immutable/entry/app.Cxgi6e_y.js",imports:["_app/immutable/entry/start.DsbP8iJ8.js","_app/immutable/chunks/NRCHeK8t.js","_app/immutable/chunks/CijBgi2q.js","_app/immutable/chunks/DkEKrC6Q.js","_app/immutable/entry/app.Cxgi6e_y.js","_app/immutable/chunks/CijBgi2q.js","_app/immutable/chunks/B2qYdWoX.js","_app/immutable/chunks/BD738dcS.js","_app/immutable/chunks/DkEKrC6Q.js","_app/immutable/chunks/BueRI3XO.js"],stylesheets:[],fonts:[],uses_env_dynamic_public:false},
		nodes: [
			__memo(() => import('../output/server/nodes/0.js')),
			__memo(() => import('../output/server/nodes/1.js')),
			__memo(() => import('../output/server/nodes/2.js'))
		],
		remotes: {
			
		},
		routes: [
			{
				id: "/",
				pattern: /^\/$/,
				params: [],
				page: { layouts: [0,], errors: [1,], leaf: 2 },
				endpoint: null
			}
		],
		prerendered_routes: new Set([]),
		matchers: async () => {
			
			return {  };
		},
		server_assets: {}
	}
}
})();
