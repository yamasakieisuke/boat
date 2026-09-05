<?php
/**
 * トップバー / ドロワー / タブバーの HTML。
 *
 * 5ページすべてが呼ぶ共通の chrome。ここだけで完結しており、
 * 呼び出し側のローカル変数には依存しない（引数で受ける）。
 */
if (!defined('ABSPATH')) exit;

function boat_forecast_viewer_render_nav($active = '', $section_code = '') {
    $archive_base = get_post_type_archive_link('forecast_day') ?: home_url('/race/');
    $archive_url  = esc_url($archive_base);
    $review_url   = esc_url(home_url('/review/'));
    $accuracy_url = esc_url(home_url('/accuracy/'));
    $player_url   = esc_url(home_url('/player/'));
    $curated_url  = esc_url(add_query_arg('filter', 'curated', $archive_base));
    $today_url    = esc_url(add_query_arg('filter', 'today', $archive_base));

    $tabs = [
        ['key' => 'archive',  'label' => '予想',   'icon' => '🏁', 'href' => $archive_url],
        ['key' => 'today',    'label' => '一覧',   'icon' => '📋', 'href' => $today_url],
        ['key' => 'review',   'label' => '結果',   'icon' => '📊', 'href' => $review_url],
        ['key' => 'accuracy', 'label' => '精度',   'icon' => '📈', 'href' => $accuracy_url],
        ['key' => 'player',   'label' => '選手',   'icon' => '👤', 'href' => $player_url],
    ];

    $section_code = (string) $section_code;
    if ($section_code === '') {
        if ($active === 'archive')       $section_code = 'FORECAST.INDEX';
        elseif ($active === 'single')    $section_code = 'RACE';
        elseif ($active === 'review')    $section_code = 'REVIEW';
        elseif ($active === 'accuracy')  $section_code = 'ACCURACY';
        elseif ($active === 'player')    $section_code = 'PLAYER';
    }

    // ── Drawer 用データ ────────────────────────────────────────────
    $venue_map = boat_forecast_viewer_venue_map();  // [slug => 日本語名]
    $drawer_main = [
        ['key' => 'archive',  'label' => '予想（会場一覧）',   'icon' => '🏁', 'href' => $archive_url],
        ['key' => 'today',    'label' => '本日のレース',       'icon' => '📋', 'href' => $today_url],
        ['key' => 'curated',  'label' => '厳選予想',           'icon' => '⭐', 'href' => $curated_url],
        ['key' => 'review',   'label' => '結果振り返り',       'icon' => '📊', 'href' => $review_url],
        ['key' => 'accuracy', 'label' => '精度ダッシュボード', 'icon' => '📈', 'href' => $accuracy_url],
        ['key' => 'player',   'label' => '選手一覧（本日）',   'icon' => '👤', 'href' => $player_url],
    ];

    // ── Drawer + Topbar 出力 ───────────────────────────────────────
    echo '<input type="checkbox" id="bfv-drawer-toggle" class="bfv-drawer-toggle" aria-hidden="true">';

    echo '<header class="bfv-topbar">';
    echo   '<label for="bfv-drawer-toggle" class="bfv-topbar-menu" role="button" tabindex="0" aria-label="メニューを開く" aria-controls="bfv-drawer-panel">☰</label>';
    echo   '<a class="bfv-topbar-brand" href="' . $archive_url . '">boat</a>';
    if ($section_code !== '') {
        echo '<span class="bfv-topbar-sep">·</span>';
        echo '<span class="bfv-topbar-section">' . esc_html($section_code) . '</span>';
    }
    echo   '<a class="bfv-topbar-action" href="' . $accuracy_url . '" aria-label="精度">📈</a>';
    echo '</header>';

    // overlay (label でも close できる)
    echo '<label for="bfv-drawer-toggle" class="bfv-drawer-overlay" aria-hidden="true"></label>';

    // drawer 本体
    echo '<aside id="bfv-drawer-panel" class="bfv-drawer-panel" role="dialog" aria-label="メインメニュー">';
    echo   '<div class="bfv-drawer-head">';
    echo     '<span>boat / メニュー</span>';
    echo     '<label for="bfv-drawer-toggle" class="bfv-drawer-close" role="button" aria-label="メニューを閉じる">×</label>';
    echo   '</div>';

    echo   '<div class="bfv-drawer-section">';
    echo     '<p class="bfv-drawer-label">主要ナビ</p>';
    echo     '<ul class="bfv-drawer-list">';
    foreach ($drawer_main as $item) {
        $cls = ($active === $item['key']) ? ' is-active' : '';
        echo '<li><a class="bfv-drawer-link' . $cls . '" href="' . $item['href'] . '">';
        echo   '<span class="bfv-drawer-link-ico" aria-hidden="true">' . $item['icon'] . '</span>';
        echo   '<span>' . esc_html($item['label']) . '</span>';
        echo '</a></li>';
    }
    echo     '</ul>';
    echo   '</div>';

    if (!empty($venue_map)) {
        echo '<div class="bfv-drawer-section">';
        echo   '<p class="bfv-drawer-label">会場ジャンプ</p>';
        echo   '<div class="bfv-drawer-grid">';
        foreach ($venue_map as $slug => $jp) {
            $vurl = esc_url(home_url('/race/' . $slug . '/'));
            echo '<a href="' . $vurl . '">' . esc_html($jp) . '</a>';
        }
        echo   '</div>';
        echo '</div>';
    }

    echo   '<div class="bfv-drawer-section">';
    echo     '<p class="bfv-drawer-label">情報</p>';
    echo     '<p class="bfv-drawer-info">boat forecast viewer<br>warm palette / IBM Plex<br>v5.20</p>';
    echo   '</div>';

    echo '</aside>';

    // ── tabbar (モバイル底部固定) ────────────────────────────────────
    // single ページは tabbar 上では「予想」(archive) として強調する
    $active_for_tab = ($active === 'single') ? 'archive' : $active;
    echo '<nav class="bfv-tabbar" role="navigation" aria-label="メインナビゲーション">';
    foreach ($tabs as $tab) {
        $is_active = ($active_for_tab === $tab['key']) ? ' is-active' : '';
        echo '<a class="bfv-tab' . $is_active . '" href="' . $tab['href'] . '">';
        echo   '<span class="bfv-tab-icon" aria-hidden="true">' . $tab['icon'] . '</span>';
        echo   '<span class="bfv-tab-label">' . esc_html($tab['label']) . '</span>';
        echo '</a>';
    }
    echo '</nav>';
}
