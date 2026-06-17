# Proxy Configs

个人代理配置项目，维护 Clash / Mihomo 和 Quantumult X 两套配置。

## 当前稳定版本

- Clash / Mihomo: `dist/clash/clash-naixi-stable.yaml`
- Quantumult X: `dist/quanx/quantumultx-naixi-stable.conf`

## 设计原则

- 机场订阅只作为节点来源
- 只保留一个手动节点选择组
- 地区节点全部使用自动切换
- AI / Telegram / Crypto / Netflix 等作为终端分流组
- Crypto 默认保留手动节点选择，避免交易场景频繁换 IP
- Premium 节点默认排除
- 流量信息节点单独放入流量看板

## 测试清单

- chatgpt.com → AI
- telegram.org → Telegram
- youtube.com → YouTube
- github.com → GitHub
- binance.com → Crypto
- baidu.com → DIRECT

## 修改流程

1. 修改 `src/`
2. 生成 `dist/`
3. 导入客户端测试
4. 通过后更新 CHANGELOG
5. 打 tag
