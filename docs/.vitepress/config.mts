import { defineConfig } from 'vitepress'

const russianSidebar = [
  {
    text: 'Начало',
    items: [
      { text: 'О Mirage', link: '/introduction' },
      { text: 'Требования', link: '/requirements' }
    ]
  },
  {
    text: 'Развёртывание',
    items: [
      { text: 'Чистый VPS', link: '/deployment/clean-vps' },
      { text: 'Подготовленный VPS', link: '/deployment/prepared-vps' },
      { text: 'Восстановление из архива', link: '/deployment/restore' }
    ]
  },
  {
    text: 'Эксплуатация',
    items: [
      { text: 'Пользователи и бот', link: '/operations/users' },
      { text: 'Резервные копии', link: '/operations/backups' },
      { text: 'Обслуживание', link: '/operations/maintenance' }
    ]
  },
  {
    text: 'Клиенты',
    items: [
      { text: 'Hiddify', link: '/clients/hiddify' },
      { text: 'Karing', link: '/clients/karing' },
      { text: 'Совместимость', link: '/clients/compatibility' }
    ]
  },
  {
    text: 'Справочник',
    items: [
      { text: 'Архитектура', link: '/reference/architecture' },
      { text: 'Порты', link: '/reference/ports' },
      { text: 'Безопасность', link: '/reference/security' }
    ]
  }
]

const englishSidebar = [
  {
    text: 'Get started',
    items: [
      { text: 'About Mirage', link: '/en/introduction' },
      { text: 'Requirements', link: '/en/requirements' }
    ]
  },
  {
    text: 'Deployment',
    items: [
      { text: 'Clean VPS', link: '/en/deployment/clean-vps' },
      { text: 'Prepared VPS', link: '/en/deployment/prepared-vps' },
      { text: 'Restore from archive', link: '/en/deployment/restore' }
    ]
  },
  {
    text: 'Operations',
    items: [
      { text: 'Users and bot', link: '/en/operations/users' },
      { text: 'Backups', link: '/en/operations/backups' },
      { text: 'Maintenance', link: '/en/operations/maintenance' }
    ]
  },
  {
    text: 'Clients',
    items: [
      { text: 'Hiddify', link: '/en/clients/hiddify' },
      { text: 'Karing', link: '/en/clients/karing' },
      { text: 'Compatibility', link: '/en/clients/compatibility' }
    ]
  },
  {
    text: 'Reference',
    items: [
      { text: 'Architecture', link: '/en/reference/architecture' },
      { text: 'Ports', link: '/en/reference/ports' },
      { text: 'Security', link: '/en/reference/security' }
    ]
  }
]

export default defineConfig({
  title: 'Mirage',
  description: 'Документация Mirage 2.0',
  lang: 'ru-RU',
  base: '/Mirage/',
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: {
    search: { provider: 'local' },
    nav: [
      { text: 'Начало', link: '/introduction' },
      { text: 'Развёртывание', link: '/deployment/clean-vps' },
      { text: 'Эксплуатация', link: '/operations/users' },
      { text: 'Клиенты', link: '/clients/hiddify' },
      { text: 'English', link: '/en/' }
    ],
    sidebar: russianSidebar,
    socialLinks: [{ icon: 'github', link: 'https://github.com/duckduckduck1/Mirage' }],
    footer: { message: 'Released under the MIT License.', copyright: 'Copyright © 2026 Mirage' }
  },
  locales: {
    root: { label: 'Русский', lang: 'ru-RU' },
    en: {
      label: 'English',
      lang: 'en-US',
      link: '/en/',
      themeConfig: {
        search: { provider: 'local' },
        nav: [
          { text: 'Get started', link: '/en/introduction' },
          { text: 'Deployment', link: '/en/deployment/clean-vps' },
          { text: 'Operations', link: '/en/operations/users' },
          { text: 'Clients', link: '/en/clients/hiddify' },
          { text: 'Русский', link: '/' }
        ],
        sidebar: englishSidebar,
        socialLinks: [{ icon: 'github', link: 'https://github.com/duckduckduck1/Mirage' }],
        footer: { message: 'Released under the MIT License.', copyright: 'Copyright © 2026 Mirage' }
      }
    }
  }
})
