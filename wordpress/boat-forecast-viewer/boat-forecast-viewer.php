<?php
/**
 * Plugin Name: Boat Forecast Viewer
 * Description: Render forecast_day posts and archives with dedicated responsive templates.
 * Version: 0.1.0
 */

if (!defined('ABSPATH')) {
    exit;
}

define('BOAT_FORECAST_VIEWER_DIR', __DIR__);
define('BOAT_FORECAST_VIEWER_URL', plugin_dir_url(__FILE__));

// 分割したファイルを読む。フック登録のタイミングを変えないよう define の直後で読む。
// ⚠️ views/ のような「呼ばれた時だけ要る」ものはここで require しないこと。
//    エントリで全部読むと、1ファイルの parse error が管理画面まで巻き込んで
//    プラグインを無効化することすらできなくなる。
require_once __DIR__ . '/inc/helpers.php';
require_once __DIR__ . '/inc/data.php';
require_once __DIR__ . '/inc/routing.php';
require_once __DIR__ . '/inc/head.php';
require_once __DIR__ . '/inc/nav.php';




























function boat_forecast_viewer_render_single($payload, $post) {
    // 本体は views/single.php（関数内 require なのでローカル変数が見える）
    require __DIR__ . '/views/single.php';
}

function boat_forecast_viewer_render_archive($query) {
    // 本体は views/archive.php（関数内 require なのでローカル変数が見える）
    require __DIR__ . '/views/archive.php';
}

function boat_forecast_viewer_render_review() {
    // 本体は views/review.php（関数内 require なのでローカル変数が見える）
    require __DIR__ . '/views/review.php';
}


function boat_forecast_viewer_render_accuracy() {
    // 本体は views/accuracy.php（関数内 require なのでローカル変数が見える）
    require __DIR__ . '/views/accuracy.php';
}


function boat_forecast_viewer_render_player() {
    // 本体は views/player.php（関数内 require なのでローカル変数が見える）
    require __DIR__ . '/views/player.php';
}


function boat_forecast_viewer_activate() {
    boat_forecast_viewer_add_rewrite_rules();
    flush_rewrite_rules();
}
register_activation_hook(__FILE__, 'boat_forecast_viewer_activate');
