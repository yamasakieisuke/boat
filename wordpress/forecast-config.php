<?php
// /web/boat/api/forecast-config.php
// forecast-sync.php から require される設定ファイル。
// heteml PHP-CGI では .htaccess SetEnv / .user.ini env[] が反映されないため、
// トークンを PHP 定数として供給する。
//
// FORECAST_SYNC_LOADER が未定義なら直接アクセスとみなし 404 を返す。
if (!defined('FORECAST_SYNC_LOADER')) {
    http_response_code(404);
    exit;
}

define('BOAT_SYNC_TOKEN', 'dslGr00chvVut1fzLEEOnyoBnjAU');
