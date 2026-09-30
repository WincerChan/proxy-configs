# AI 链式代理

两套配置的 `🤖 AI` 均固定使用 `land-jp`。实际连接顺序为：本机 → `♾️ 中转` 选中的机场节点 → `land-jp` → 目标网站。中转线路可以单独切换。

## Mihomo

`♾️ 中转` 直接列出当前配置中的机场节点，手动选择，不再嵌套地区自动组或节点选择组。导入后在该组选择一个可用机场节点，重启代理服务后检查 VPS 新连接的来源 IP；本次调整尚未确认解决 FlClash 的实际中转问题。

在客户端最终合并配置的顶层 `proxies` 列表中添加完整节点，名称必须是 `land-jp`，节点上必须设置 `dialer-proxy: ♾️ 中转`。例如，已有节点定义需包含以下字段（不是可独立导入的完整节点）：

```yaml
proxies:
  - name: land-jp
    server: jp.land.itswincer.net
    dialer-proxy: ♾️ 中转
    # 另行填写实际协议 type、端口 port 及认证等协议参数
```

仅填写名称不会启用中转；`dialer-proxy` 必须设置在落地节点上，不能设置在策略组上。不要给机场中转节点添加这个字段，以免中转节点引用自身。

机场节点和落地节点统一粘贴到 `src/clash/10-proxies.yaml` 的 `proxies` 列表，再生成配置；也可直接编辑客户端当前配置中的同一列表。节点选择与地区自动组使用 `include-all-proxies: true`，从当前配置的节点按名称筛选，不再依赖 Naixi provider。所有中转候选组排除 `land-` 开头的节点，避免落地节点进入中转链。

仓库不包含节点凭据；必须先合并该节点再加载配置，否则 Mihomo 会因找不到 `land-jp` 而拒绝加载。当前采用顶层节点名称引用；若改用独立 proxy-provider，需要相应调整 AI 组的 `use` 和节点过滤。

## Quantumult X

QX 的中转组仍默认日本自动。节点选择、全局自动测速、故障切换及各地区自动组均排除 `land-` 开头的节点（不区分大小写），避免落地节点成为自身的中转；AI 组仍直接引用 `land-jp`。

单独添加名为 `land-jp` 的落地节点，地址使用 `land.itswincer.net` 或其子域名，例如 `jp.land.itswincer.net`。不要把落地节点混入中转组的机场节点资源。

本地 AI 规则已添加 `via-interface=%TUN%`；远程 AI 规则通过 KOP-XIAO 资源解析器转换并添加该参数。导入后刷新远程规则，并检查生成的 AI 规则包含该参数。

落地地址通过 `host-suffix, land.itswincer.net, ♾️ 中转` 匹配。需在 QX 日志确认回注后的连接命中这条规则。

## 客户端验证

访问 AI 网站，在连接记录确认落地是 `land-jp`、前置是中转组选择的机场节点。也可检查落地服务器的入站连接来源是否为机场出口。仅检查最终出口 IP 不能区分直连落地和经过中转。

## AI 规则来源

两端统一使用 MetaCubeX `category-ai-!cn` 综合 AI 分类，每 86400 秒更新。覆盖 OpenAI、Anthropic/Claude、Gemini、Perplexity、Poe、Copilot，以及 Cursor、Grok、其他 AI 工具与相关基础设施；范围随上游维护变化，不代表所有 AI 网站或中国境内 AI 服务的完整清单。

- Mihomo：`https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/category-ai-!cn.mrs`，在 Google、Microsoft、GitHub 等通用规则之前匹配。
- QX：同路径的 `category-ai-!cn.list`，在通用远程规则之前匹配，强制策略为 `🤖 AI`。
- 本地保留原有服务域名补充，并明确补齐 Claude 域名；移除 `claude`、`anthropic`、`openai`、`chatgpt` 的宽泛关键词匹配，避免同名无关域名误入 AI。

QX 解析参数 `type=domain-set` 保留普通域名的精确匹配。上游 `+.` 表示域名本身及子域名，因此 `replace` 参数解码后为 `^host, \+\.@host-suffix, `，将该格式转换成 `host-suffix`；`via=%TUN%` 为全部转换结果添加回注参数。不要直接删掉转换参数或改用未经验证的 YAML 自动转换：当前解析器会把未加引号的 `+.` 错转为通配符规则。
