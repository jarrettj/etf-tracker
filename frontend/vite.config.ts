import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		port: 5175,
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8002',
				changeOrigin: true,
			},
		},
	},
});
