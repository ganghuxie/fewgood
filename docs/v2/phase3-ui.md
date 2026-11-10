# Phase 3：静态 topic 与我的空间

在 `site/` 中运行 `npm run build`；它会先从 `public/topics/*.json` 确定性地生成 `src/data/topic-video-catalog.json`，再生成 catalog 和静态页面。公开 topic fixture 在 `site/public/topics/`，索引在 `site/src/data/topics/index.json`。

本地查看：`cd site/dist && python3 -m http.server 4173`，打开 `http://127.0.0.1:4173/youtuber/?mockTopics=1`。`mockTopics=1&emptyTopics=1` 显示已登录但没有自定义主题的状态；不带 mock 参数是退出登录的公开浏览/登录 CTA 状态。

截图示例：`google-chrome --headless --no-sandbox --window-size=1280,900 --screenshot=../screenshots/v2_space_1280.png 'http://127.0.0.1:4173/youtuber/?mockTopics=1'`。390px 截图同理替换窗口尺寸与文件名。

仍需 Jason：配置真实 staging Supabase anon URL/key 并验证 live RPC；后续授权后再启用 topic refresh schedule，以及合并 master。这里没有使用 service role、真实账号或 YouTube API。
