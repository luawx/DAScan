# Cache Design

缓存根目录是 `cache/`，结构为 `cache/<project>/<YYYYMMDD>/{images,metadata,thumbnails}`。第一版实现 images 和 metadata；文件名附加远程路径 SHA-256 的短摘要，避免同名冲突。

图片浏览以 `index.json` 中的 `created_at` 判断缓存是否仍然有效。图片及对应 metadata 均命中时，切图不会建立 SSH/SFTP 连接；缓存缺失或服务器记录变化时才下载。预览操作仍读取服务器 sidecar metadata。内容更新使用临时文件和原子替换，缓存不修改服务器文件。
