# AI 链式代理

两套配置的 `🤖 AI` 均固定使用 `land-jp`。实际连接顺序为：本机 → `♾️ 中转` 选中的机场节点 → `land-jp` → 目标网站。中转组默认日本自动，可单独切换线路。

## Mihomo

在客户端最终合并配置的顶层 `proxies` 列表中添加完整节点，名称必须是 `land-jp`，节点上必须设置 `dialer-proxy: ♾️ 中转`。例如，已有节点定义需包含以下字段（不是可独立导入的完整节点）：

```yaml
proxies:
  - name: land-jp
    server: jp.land.itswincer.net
    dialer-proxy: ♾️ 中转
    # 另行填写实际协议 type、端口 port 及认证等协议参数
```

仅填写名称不会启用中转；`dialer-proxy` 必须设置在落地节点上，不能设置在策略组上。不要对机场 Naixi provider 整体添加这个覆盖项，以免中转节点引用自身。

仓库不包含落地节点凭据；必须先合并该节点再加载配置，否则 Mihomo 会因找不到 `land-jp` 而拒绝加载。当前采用顶层节点名称引用；若改用独立 proxy-provider，需要相应调整 AI 组的 `use` 和节点过滤。

## Quantumult X

单独添加名为 `land-jp` 的落地节点，地址使用 `land.itswincer.net` 或其子域名，例如 `jp.land.itswincer.net`。不要把落地节点混入中转组的机场节点资源。

本地 AI 规则已添加 `via-interface=%TUN%`；远程 OpenAI 规则通过 KOP-XIAO 资源解析器添加该参数。导入后刷新远程规则，并检查生成的 OpenAI 规则包含该参数。

落地地址通过 `host-suffix, land.itswincer.net, ♾️ 中转` 匹配。需在 QX 日志确认回注后的连接命中这条规则。

## 客户端验证

访问 AI 网站，在连接记录确认落地是 `land-jp`、前置是中转组选择的机场节点。也可检查落地服务器的入站连接来源是否为机场出口。仅检查最终出口 IP 不能区分直连落地和经过中转。
