/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

// 允许 `import url from '/foo.png?url'` 形式拿到资源的最终 URL
declare module '*.png?url' {
  const src: string
  export default src
}
