// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// Determine base path based on environment
// - Local dev: /
// - PR preview: /kartograph/pr-preview/pr-{number}
// - Production: /kartograph
const getBasePath = () => {
	if (process.env.PR_PREVIEW_PATH) {
		return process.env.PR_PREVIEW_PATH;
	}
	return process.env.CI ? '/kartograph/' : '/';
};

// https://astro.build/config
export default defineConfig({
	site: 'https://openshift-hyperfleet.github.io',
	base: getBasePath(),
	integrations: [
		mermaid({
			theme: 'neutral',
			autoTheme: true
		}),
		starlight({
			title: 'Kartograph',
			description: 'Enterprise knowledge graph platform with secure enclave pattern',
			logo: {
				src: './src/assets/kartograph-logo.png',
			},
			lastUpdated: true,
			editLink: {
				baseUrl: 'https://github.com/openshift-hyperfleet/kartograph/edit/main/website/',
			},
			components: {
				ThemeProvider: './src/components/ThemeProvider.astro',
				SiteTitle: './src/components/SiteTitle.astro',
				Footer: './src/components/Footer.astro',
			},
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/openshift-hyperfleet/kartograph',
				},
			],
			favicon: '/favicon.ico',
			sidebar: [
				{
					label: 'Getting Started',
					items: [
						{ label: 'Introduction', slug: '' },
						{ label: 'Quick Start', slug: 'getting-started/quickstart' },
					],
				},
				{
					label: 'Guides',
					items: [
						{
							label: 'Extraction → Graph Mutations',
							slug: 'guides/extraction-mutations',
						},
					],
				},
				{
					label: 'Reference',
					items: [
						{ label: 'Mutation Operation Schema', slug: 'reference/mutation-schema' },
						{ label: 'Secure Enclave ID Design', slug: 'reference/secure-enclave' },
					],
				},
				{
					label: 'Architecture',
					items: [
						{ label: 'Bounded Contexts', slug: 'architecture/bounded-contexts' },
						{ label: 'DDD Patterns', slug: 'architecture/ddd-patterns' },
					],
				},
			],
			customCss: [
				'./src/styles/custom.css',
			],
		}),
	],
});
