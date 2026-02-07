# YouTube データ管理

更新タイミングごとにフォルダを作成し、CSVファイルでYouTubeデータを管理します。

## フォルダ構造

```
youtube/
├── README.md
├── 2026-02-08/          ← 更新日付フォルダ
│   ├── channels.csv     ← チャンネル情報
│   └── videos.csv       ← 動画情報（URLリンク付き）
├── 2026-02-15/          ← 次回更新時に作成
│   ├── channels.csv
│   └── videos.csv
└── ...
```

## CSVフォーマット

### channels.csv
| カラム | 説明 |
|--------|------|
| party_id | 政党ID |
| channel_name | チャンネル名 |
| channel_id | YouTubeチャンネルID |
| channel_url | チャンネルURL |
| subscriber_count | 登録者数 |
| video_count | 動画数 |
| total_views | 総視聴回数 |

### videos.csv
| カラム | 説明 |
|--------|------|
| title | 動画タイトル |
| video_url | YouTube動画URL |
| party_mention | 関連政党ID |
| issue_category | イシューカテゴリ |
| channel_party_id | チャンネル所属政党ID |
| published_date | 公開日 |

## 更新手順

1. 新しい日付フォルダを作成 (例: `2026-02-15/`)
2. `channels.csv` と `videos.csv` を配置
3. `videos.csv` の `video_url` に正しいYouTubeリンクを設定
4. バックエンドを再起動するとシードデータが更新される

## 注意

- `video_url` が `PLACEHOLDER` を含む場合、フロントエンドではリンクなしで表示されます
- 最新の日付フォルダが自動的に読み込まれます
