# Latch 分流配置

新增第三个构建目标 `dist/latch/latch-naixi-stable.yaml`，使用 Latch 现有的「导入分流配置」入口。这是分流导入文件，不是直接交给 `latch-kernel` 的完整 JSON 启动配置。节点仍由客户端的订阅或手动添加维护。

## 格式选择

2026-10-05 核对了 Mihomo 源模板引用的 26 个 MetaCubeX MRS 规则集：同路径的 `.yaml` 都能下载，均包含字符串 `payload`。因此使用同源 YAML，不引入 MRS 解压、域名集合和 CIDR 集合的二进制解析。规则顺序、内容类型和更新间隔沿用 Mihomo 源模板。

中国域名 YAML 当日为 111,224 条、2,297,964 字节。Latch 原有 65,536 条上限不足，需使用扩大条目上限的内核；4 MiB 下载限制继续保留。原有 Apple_All.yaml 地址返回 404，Latch 单独改用同项目的 Apple_Classical.yaml；不重写已有 Mihomo / QX 配置。

## 策略如何映射

Latch 的节点组是「节点名称匹配 + 手动成员」，不能嵌套另一节点组或 DIRECT。构建时保留原有按地区等条件匹配节点的组，将 `exclude-filter` 合并进匹配表达式；终端策略组则递归展开所选策略，流量规则直接指向对应节点组或 DIRECT / REJECT。

`src/latch/profile.json` 的 `policyTargets` 可指定某个策略组使用它原列表中的哪个候选；未指定时使用源模板的第一项。因此新配置保持源模板的默认去向，但不复制 Mihomo 的终端策略组选择界面。以后在 Latch 内可直接编辑流量规则出口，或修改 `policyTargets` 后重新构建。

例如将 Telegram 默认出口改成日本自动：`"policyTargets": {"✈️ Telegram": "🇯🇵 日本自动"}`。不支持的候选和递归策略循环会让构建失败。源模板的组测速 tolerance、timeout、lazy 等不导入；Latch 使用自身的节点组测速设置。规则集的 `proxy: 🚀 代理` 不导入，因为 Latch 规则集没有逐项下载代理字段；现有内核规则集下载使用直连，不能宣称与 Mihomo 的下载出口相同。

`🤖 AI` 保留为只匹配 `land-jp` 的节点组。导入文件只携带 `land-jp → ♾️ 中转` 的链式关系，不携带密码。客户端应先导入真实节点；缺少落地或中转节点时应拦截，不能回退到直连。中转匹配表达式排除 `land-`、Premium 与流量信息节点。

## 验证要求

- 构建保持现有 Clash / QX 产物不变，CI 校验及发布第三个文件。
- 检查全部规则的目标、引用和唯一末尾 MATCH，策略选择无循环。
- 使用 Latch 共享导入、编译接口核验地区匹配、排除条件、缺失引用和链式路径。
- 保留 RULE-SET 上的 `no-resolve`，内核将它作用于名单中的 IP / GEOIP 条目。
- 验证超过旧条目上限的中国域名名单及全部远程规则集可加载。
- 待补：用户设备上的真实节点、凭据及链式出口验收；自动验证不得使用真实节点凭据或修改客户端当前配置。

## 使用

先在 Latch 的节点页导入机场节点，并添加名为 `land-jp` 的真实落地节点；当前 Latch 内核支持 Trojan / AnyTLS。随后在分流页「更多 → 导入分流配置」选择生成的 YAML，再切换到导入的分流配置。客户端已有同名节点组会按现有契约保留，导入前请确认它们的名称匹配条件正确，或使用新的空白测试数据目录。

运行 `python3 scripts/validate-latch.py --online` 可检查当前上游名单。若有 Latch 工程构建的 CLI，可追加 `--business /path/to/latch-business --kernel /path/to/latch-kernel`，验证真实导入、匹配、链式方向、缺失落地拦截及全部真实名单的内核加载。此验证只使用受控的虚构节点，不修改客户端数据或连接用户代理。

Windows 可用 `--business-dll C:\path\core\latch-core.dll` 代替 CLI，调用纯业务 ABI，不创建客户端。2026-10-05 已验证随包 build86 DLL 与新 Windows 内核，以及 Linux business CLI / 新内核：16 个节点组、27 个真实名单和 152 条规则均通过；中国域名 111,224 条。29 个生成器回归通过，旧两套 dist 文件内容不变。用户实机与真实中转验收仍待补。
