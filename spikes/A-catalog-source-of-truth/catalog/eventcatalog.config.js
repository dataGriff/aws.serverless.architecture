/** @type {import('@eventcatalog/core/bin/eventcatalog.config').Config} */
export default {
  title: 'EventCatalog',
  tagline:
    'This internal platform provides a comprehensive view of our event-driven architecture across all systems. Use this portal to discover existing domains, explore services and their dependencies, and understand the message contracts that connect our infrastructure',
  organizationName: 'Platform',
  theme: 'sunset',
  homepageLink: 'https://eventcatalog.dev/',
  editUrl: 'https://github.com/boyney123/eventcatalog-demo/edit/master',
  // Supports static or server. Static renders a static site, server renders a server side rendered site
  // large catalogs may benefit from server side rendering
  output: 'static',
  // By default set to false, add true to get urls ending in /
  trailingSlash: false,
  // GitHub Pages serves the site under /<repo>; the pages workflow sets EVENTCATALOG_BASE. Local dev stays at /.
  base: process.env.EVENTCATALOG_BASE ?? '/',
  // Resource search is the default lightweight search. Change this to { type: 'indexed' }
  // to enable full-content search. Indexed search requires running a build to generate the index.
  search: {
    type: 'resource',
  },
  // Customize the navigation for your docs sidebar.
  // read more at https://eventcatalog.dev/docs/development/customization/customize-sidebars/documentation-sidebar
  navigation: {
    pages: ['list:all'],
  },
  // Customize the logo, add your logo to public/ folder
  logo: {
    alt: 'EventCatalog Logo',
    src: '/logo.png',
    text: 'EventCatalog',
  },
  // This lets you copy markdown contents from EventCatalog to your clipboard
  // Including schemas for your events and services
  llmsTxt: {
    enabled: true,
  },
  // required random generated id used by eventcatalog
  cId: '08da9a7e-1de9-49bf-aa16-2379dde4f26f',
  // required by eventcatalog
  tsd: 1791126576671,
};
