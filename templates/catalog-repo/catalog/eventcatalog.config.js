/** @type {import('@eventcatalog/core/bin/eventcatalog.config').Config} */
// platform.yaml: organisation_name, catalog_edit_url, catalog_site_url
export default {
  title: 'Platform catalog',
  tagline: 'The source of truth for every domain, service, event, command, query and data product. A PR here is how you publish an event, subscribe to one, or expose an API.',
  organizationName: 'Platform',
  theme: 'sunset',
  homepageLink: 'https://eventcatalog.dev/',
  editUrl: 'https://github.com/example/catalog/edit/main',
  output: 'static',
  trailingSlash: false,
  // GitHub Pages serves the site under /<repo>; the pages workflow sets EVENTCATALOG_BASE. Local dev stays at /.
  base: process.env.EVENTCATALOG_BASE ?? '/',
  search: { type: 'resource' },
  navigation: { pages: ['list:all'] },
  logo: { alt: 'Platform catalog', src: '/logo.png', text: 'Platform catalog' },
  // Copy page contents as markdown for an agent, and publish llms.txt with the site
  llmsTxt: { enabled: true },
  // required random generated id used by eventcatalog — regenerate with `npx @eventcatalog/create-eventcatalog` or keep
  cId: '3f0c2c2e-6a6b-4d5c-9c1a-7e8f0b1c2d3e',
  tsd: 1791126576671,
};
