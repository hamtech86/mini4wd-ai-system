-- ============================================================
-- triggers.sql
-- Mini4WD System
-- SQLite3
--
-- 現在トリガーは使用しない
--
-- 理由
-- ・updated_at は Repository が管理
-- ・評価計算は Analysis Engine が担当
-- ・キャッシュ更新は DatabaseManager が担当
--
-- 将来SQLite側で処理が必要になった場合のみ追加する
-- ============================================================

PRAGMA foreign_keys = ON;

