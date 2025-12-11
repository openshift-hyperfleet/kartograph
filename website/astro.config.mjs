// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// https://astro.build/config
export default defineConfig({
	site: 'https://openshift-hyperfleet.github.io',
	base: process.env.CI ? '/kartograph' : '/',
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
			components: {
				ThemeProvider: './src/components/ThemeProvider.astro',
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
