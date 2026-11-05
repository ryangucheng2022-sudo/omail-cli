# omail

[English](README.md) | 简体中文

单文件、零依赖的 Microsoft 365 邮箱命令行工具：完整的邮件管理（读取、搜索、摘要、附件、发送/回复/标记/移动/删除）与日程管理（查询、创建、修改、删除），全部走 Outlook REST API v2.0。

**适用**：Microsoft 365 全球版与世纪互联版（中国版）租户。**不需要租户管理员同意**——借 Microsoft Office 第一方应用的预置权限走设备码流程，你用自己的账号登录一次即可。

## 功能一览

- **邮件**：文件夹与计数、列表、全文搜索、读正文（可截断）、晨间摘要（digest）、附件列表与下载
- **写邮件**：发送（支持多附件）、回复、标记已读/未读、移动、删除（含永久删除）
- **日程**：日历列表、时间窗查询、单个日程，以及创建/修改/删除（带参会人即发邀请）
- **自动分页**：列表类命令跟随 `@odata.nextLink` 拉齐全部结果，不会因单页上限漏数据
- **写操作安全设计**：发送前参数校验、`--dry-run` 预览模式、幂等防重复（见下）
- **零依赖**：一个 Python 文件，标准库实现；输出全是 JSON，方便脚本和 AI 智能体调用

## 云支持状态

- **世纪互联（中国）——正式支持**。默认云，Outlook REST API v2.0（partner.outlook.cn），本工具即针对该配置开发与测试。
- **全球版——旧配置，按现状提供**。`global` 配置指向 outlook.office365.com 的 Outlook REST API v2.0；微软已在全球云弃用该 API 并转向 Microsoft Graph、正在退役，因此该配置随时可能失效，且**未**对当前全球端点做过验证。请当作起点参考，而非受支持配置。
- Microsoft Graph 后端是未来可能的方向，不属于本版本；当前设计停留在 v2.0 接口面，正是因为「免管理员同意的设备码模式」依赖它尚可用的云。

## 环境要求

- Python 3.9+（仅标准库，无需 pip 安装任何东西）
- 能访问所在云的登录与 API 域名（经代理时自动读取 `https_proxy` / `HTTPS_PROXY` 环境变量，大小写都认）

## 快速开始

```bash
chmod +x bin/omail
bin/omail auth --email you@yourcompany.com
# 按提示打开网址、输入设备码，用公司账号登录
bin/omail doctor   # 自检：输出你的账号与收件箱计数即通
```

全球版 Microsoft 365（旧配置，见「云支持状态」）：`bin/omail auth --email you@yourcompany.com --cloud global`

租户 ID 会从你的邮箱域名自动发现，无需手填（可用 `--tenant <guid>` 覆盖）。

## 工作原理

- **服务模型**：全部走世纪互联运营的 Microsoft 365 主权云（partner.outlook.cn）上的 Outlook REST API v2.0，不依赖 IMAP、EWS 或 Graph——邮件、日历、通讯录共用一套接口。
- **认证模型**：OAuth 2.0 设备码流程，借用 Microsoft Office 第一方应用客户端。这是有意选择：不需要注册自有应用、不需要租户管理员同意，在不批准自建应用注册的组织里也能用。刷新令牌本地存储（权限 600）且每次刷新轮换；重新授权只需一条交互式 `reauth` 命令。
- **传输**：HTTP 走手工 CONNECT 隧道，因为标准库的代理处理在部分企业出口代理后面不可靠。
- **安全模型**：读命令只输出 JSON、不改任何东西；写命令（发送、回复、删除、建日程等）支持 `--dry-run`（只校验和预览、不调接口），并有日志防重，网络重试不会把一封邮件发两遍、日程建两个。
- **为什么是 CLI**：一次登录之后，每条命令都非交互、输出机器可读——这是 AI Agent（和定时任务）可靠操作邮箱所需的形态。

## 命令一览

只读：

| 命令 | 用途 |
|---|---|
| `doctor` | 自检＋收件箱计数 |
| `folders` | 文件夹与计数 |
| `list [--folder 名称] [--unread] [--top N]` | 邮件列表（默认收件箱） |
| `search "关键词" [--top N]` | 全邮箱搜索（主题＋正文） |
| `read <id> [--body-max N]` | 读一封；`--body-max N` 把正文截断到 N 字符（截断时输出带 `body_truncated: true`） |
| `attachments <id>` / `attachment-get <id> <附件Id> <路径>` | 附件列表 / 下载 |
| `digest <ISO时间>` | 某时间点之后的新增未读（晨间摘要场景） |
| `calendar [--days N]` / `calendars` / `event <id>` | 日程窗口 / 日历列表 / 单个日程（时间为 UTC） |
| `contacts [--search KW] [--top N]` | 个人通讯录（姓名/邮箱/公司/职位/部门；不支持电话字段） |
| `find 关键词 [--top N]` | 查人：全局地址簿搜索＋个人通讯录匹配合并（带 `sources` 来源标注）；中文全名在目录侧偶有漏检，按邮箱前缀最可靠 |

写（不可逆，自动化场景请先经人工确认）：

| 命令 | 用途 |
|---|---|
| `send --to A [--cc C] --subject S --body B \| --body-file F [--attach 路径1,路径2]` | 发信，可带附件 |
| `reply <id> --body B` | 回复（自动 RE:） |
| `mark <id> --read \| --unread` | 标已读/未读（两个标志必须恰好给一个） |
| `move <id> --folder 文件夹名` | 移动（移动后消息 Id 会变化，后续操作先重新搜索定位） |
| `delete <id>` | 删除；在「已删除邮件」里再 delete 为永久删除 |
| `event-create --subject S --start ISO --end ISO [--tz 时区] [--location L] [--body B] [--attendees 邮箱,邮箱] [--calendar 日历Id]` | 新建日程；时间填本地时刻，`--tz` 为 Windows 时区名（默认 `China Standard Time`）；**带 attendees 即向参会人发送邀请** |
| `event-update <id> [同上字段]` | 修改日程（只传要改的字段） |
| `event-delete <id>` | 删除日程（有参会人时会发取消通知） |

## 写操作的安全设计

- **预览模式**：所有写命令都可加 `--dry-run`——只做参数校验并输出「将要执行的动作」JSON，不取令牌、不调 API。自动化场景建议先 dry-run 给人看，再正式执行。
- **参数校验**：必填项、邮箱格式、时间格式与先后关系、附件/正文文件存在性都在发请求前校验，不合格报 `usage` 错（退出码 64），不把坏请求打到服务器。
- **防重复（幂等）**：网络层对写请求不做盲目重试——请求已发出后若响应丢失，报 `ambiguous_outcome`（退出码 3）提示先核实，不要直接重跑。另外 `send` 与 `event-create` 有本地幂等日志（`write_journal.json`，与令牌同目录）：10 分钟内完全相同的操作会被拦截；确认确实没发成/没建成时，加 `--force` 放行。

## 令牌与安全

- 授权后刷新令牌存 `token_store.json`（自动轮换，文件权限 600）。存放位置：设了环境变量 `OMAIL_HOME` 时在其目录下；否则优先包目录、再否则 `~/.omail/`。
- **刷新令牌等同于邮箱密码**：不要分享、不要提交代码仓库、不要在多台机器间拷贝——换机器重新 `auth` 即可。（仓库自带 `.gitignore` 已排除该文件。）
- 令牌失效（命令报 `token_invalid`、退出码 2）时，重新运行 `omail auth --email ...` 输一次设备码即可恢复。

## 已知限制

- 能否授权取决于租户是否为 Office 第一方应用预置了 OutlookService 权限，绝大多数 M365 租户可以；个别租户登录会报 AADSTS65002，此时本路线不通、需联系管理员，不要尝试用自注册应用绕行。
- 使用 Outlook REST API v2.0（非 Microsoft Graph），全球版与世纪互联端点均已内置。
- `calendar` 返回时间为 UTC，展示时请自行换算本地时区；`event-update` 后服务端可能把起止时间以 UTC 呈现，实际时刻不变。
- 日程删除是硬删除（不进回收站），删前请确认 Id 无误。

## 测试

```bash
python3 -m unittest discover -s tests -v   # 39 个用例，全离线，不需要账号
```

## 版本

完整变更记录见 [CHANGELOG.md](CHANGELOG.md)。当前版本 **v1.2.2**。

## 许可证

MIT — 见 [LICENSE](LICENSE)。
