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

function boat_forecast_viewer_favicon_href() {
    return BOAT_FORECAST_VIEWER_URL . 'assets/boat-favicon.svg';
}

function boat_forecast_viewer_render_favicon() {
    $href = esc_url(boat_forecast_viewer_favicon_href());
    echo '<link rel="icon" type="image/svg+xml" href="' . $href . '">' . "\n";
    echo '<link rel="shortcut icon" href="' . $href . '">' . "\n";
    echo '<link rel="apple-touch-icon" href="' . $href . '">' . "\n";
}
add_action('wp_head', 'boat_forecast_viewer_render_favicon', 1);
add_action('admin_head', 'boat_forecast_viewer_render_favicon', 1);
add_action('login_head', 'boat_forecast_viewer_render_favicon', 1);

function boat_forecast_viewer_venue_map() {
    return [
        'kiryu' => '桐生',
        'toda' => '戸田',
        'edogawa' => '江戸川',
        'heiwajima' => '平和島',
        'tamagawa' => '多摩川',
        'hamanako' => '浜名湖',
        'gamagori' => '蒲郡',
        'tokoname' => '常滑',
        'tsu' => '津',
        'mikuni' => '三国',
        'biwako' => 'びわこ',
        'suminoe' => '住之江',
        'amagasaki' => '尼崎',
        'naruto' => '鳴門',
        'marugame' => '丸亀',
        'kojima' => '児島',
        'miyajima' => '宮島',
        'tokuyama' => '徳山',
        'shimonoseki' => '下関',
        'wakamatsu' => '若松',
        'ashiya' => '芦屋',
        'fukuoka' => '福岡',
        'karatsu' => '唐津',
        'omura' => '大村',
    ];
}

function boat_forecast_viewer_add_rewrite_rules() {
    $venue_pattern = implode('|', array_keys(boat_forecast_viewer_venue_map()));
    add_rewrite_rule('^race/(' . $venue_pattern . ')/?$', 'index.php?post_type=forecast_day&bfv_venue=$matches[1]', 'top');
    add_rewrite_rule('^review/?$', 'index.php?bfv_review=1', 'top');
}
add_action('init', 'boat_forecast_viewer_add_rewrite_rules');

function boat_forecast_viewer_query_vars($vars) {
    $vars[] = 'bfv_venue';
    $vars[] = 'bfv_review';
    return $vars;
}
add_filter('query_vars', 'boat_forecast_viewer_query_vars');

function boat_forecast_viewer_pre_get_posts($query) {
    if (is_admin() || !$query->is_main_query()) {
        return;
    }
    if (!$query->is_post_type_archive('forecast_day')) {
        return;
    }
    $venue_slug = $query->get('bfv_venue');
    if (!$venue_slug) {
        return;
    }
    $query->set('post_type', 'forecast_day');
    $query->set('posts_per_page', -1);
    $query->set('meta_key', 'venue_slug');
    $query->set('meta_value', $venue_slug);
    $query->set('order', 'DESC');
}
add_action('pre_get_posts', 'boat_forecast_viewer_pre_get_posts');

function boat_forecast_viewer_collect_archive_items() {
    $posts = get_posts([
        'post_type' => 'forecast_day',
        'post_status' => 'publish',
        'numberposts' => -1,
        'orderby' => 'date',
        'order' => 'DESC',
    ]);

    $venues = [];
    foreach ($posts as $post) {
        $payload = boat_forecast_viewer_load_payload($post->ID);
        $venue_slug = isset($payload['venue_slug']) ? (string) $payload['venue_slug'] : (string) get_post_meta($post->ID, 'venue_slug', true);
        if ($venue_slug === '') {
            continue;
        }
        $venue_name = isset($payload['venue_name']) ? (string) $payload['venue_name'] : (string) get_post_meta($post->ID, 'venue_name', true);
        $race_date = isset($payload['date']) ? (string) $payload['date'] : (string) get_post_meta($post->ID, 'race_date', true);
        if (!isset($venues[$venue_slug])) {
            $venues[$venue_slug] = [
                'slug' => $venue_slug,
                'name' => $venue_name !== '' ? $venue_name : ($venue_slug),
                'count' => 0,
                'review_count' => 0,
                'latest_date' => '',
                'latest_link' => '',
                'items' => [],
            ];
        }
        $venues[$venue_slug]['count'] += 1;
        if (!empty($payload['review_summary'])) {
            $venues[$venue_slug]['review_count'] += 1;
        }
        if ($venues[$venue_slug]['latest_date'] === '' || $race_date > $venues[$venue_slug]['latest_date']) {
            $venues[$venue_slug]['latest_date'] = $race_date;
            $venues[$venue_slug]['latest_link'] = get_permalink($post);
        }
        $venues[$venue_slug]['items'][] = [
            'title' => get_the_title($post),
            'link' => get_permalink($post),
            'date' => $race_date,
            'has_review' => !empty($payload['review_summary']),
        ];
    }

    foreach ($venues as $slug => $venue) {
        usort($venue['items'], function ($a, $b) {
            return strcmp((string) $b['date'], (string) $a['date']);
        });
        $venue['items'] = array_slice($venue['items'], 0, 4);
        $venues[$slug] = $venue;
    }

    uasort($venues, function ($a, $b) {
        return strcmp((string) $b['latest_date'], (string) $a['latest_date']);
    });

    return $venues;
}

function boat_forecast_viewer_grade_class($grade) {
    $grade = strtoupper((string) $grade);
    if ($grade === 'A1') {
        return 'grade-a1';
    }
    if ($grade === 'A2') {
        return 'grade-a2';
    }
    return 'grade-b';
}

function boat_forecast_viewer_render_grade($grade) {
    $grade = (string) $grade;
    if ($grade === '') {
        return '';
    }
    return sprintf('<span class="bfv-grade %s">%s</span>', esc_attr(boat_forecast_viewer_grade_class($grade)), esc_html($grade));
}

function boat_forecast_viewer_waku_colors($waku) {
    $waku = (int) $waku;
    $map = [
        1 => ['#ffffff', '#222222', '#c9c9c9'],
        2 => ['#111111', '#ffffff', '#111111'],
        3 => ['#d73030', '#ffffff', '#d73030'],
        4 => ['#2f6fd6', '#ffffff', '#2f6fd6'],
        5 => ['#f0d44c', '#222222', '#d3b11f'],
        6 => ['#4aa35c', '#ffffff', '#4aa35c'],
    ];
    return isset($map[$waku]) ? $map[$waku] : ['#eef3ff', '#222222', '#c8d4f0'];
}

function boat_forecast_viewer_render_waku_name($waku, $name, $is_female) {
    list($bg, $fg, $border) = boat_forecast_viewer_waku_colors($waku);
    $female = !empty($is_female) ? '<span class="bfv-female">♥</span>' : '';
    return sprintf(
        '<span class="bfv-waku-name-cell"><span class="bfv-waku-chip" style="background:%s;color:%s;border-color:%s;">%s</span><span class="bfv-waku-name">%s%s</span></span>',
        esc_attr($bg),
        esc_attr($fg),
        esc_attr($border),
        esc_html((string) $waku),
        $female,
        esc_html((string) $name)
    );
}

function boat_forecast_viewer_load_payload($post_id) {
    $raw = get_post_meta($post_id, 'forecast_payload', true);
    if (!is_string($raw) || $raw === '') {
        return [];
    }
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function boat_forecast_viewer_render_badge($active, $label) {
    $class = $active ? 'bfv-badge is-on' : 'bfv-badge';
    return sprintf(
        '<span class="%s">%s</span>',
        esc_attr($class),
        esc_html($label)
    );
}

function boat_forecast_viewer_conf_class($label) {
    if ($label === 'high') {
        return 'is-conf-high';
    }
    if ($label === 'mid') {
        return 'is-conf-mid';
    }
    return 'is-conf-low';
}

function boat_forecast_viewer_mark_for_rank($rank) {
    $rank = (int) $rank;
    if ($rank === 1) {
        return '◎';
    }
    if ($rank === 2) {
        return '○';
    }
    if ($rank === 3) {
        return '▲';
    }
    if ($rank === 4) {
        return '✕';
    }
    return '';
}

function boat_forecast_viewer_render_meter($value, $max, $class) {
    $num = is_numeric($value) ? (float) $value : 0.0;
    $max_num = is_numeric($max) && (float) $max > 0 ? (float) $max : 100.0;
    $pct = max(0.0, min(100.0, ($num / $max_num) * 100.0));
    return sprintf(
        '<span class="bfv-meter %s"><span class="bfv-meter-fill" style="width:%s%%"></span></span>',
        esc_attr($class),
        esc_attr((string) round($pct, 1))
    );
}

function boat_forecast_viewer_render_exhibition_text($raw) {
    if (!is_array($raw)) {
        return '未取得';
    }
    $parts = [];
    if (!empty($raw['time'])) {
        $parts[] = 'T ' . $raw['time'];
    }
    if (!empty($raw['start_timing'])) {
        $parts[] = 'ST ' . $raw['start_timing'];
    }
    if (!empty($raw['tilt'])) {
        $parts[] = 'チルト ' . $raw['tilt'];
    }
    if (!empty($raw['entry_course'])) {
        $parts[] = '進入 ' . $raw['entry_course'];
    } elseif (!empty($raw['actual_course'])) {
        $parts[] = '進入 ' . $raw['actual_course'];
    }
    if (!empty($raw['prev_rank'])) {
        $parts[] = '前走 ' . $raw['prev_rank'] . '着';
    }
    if (!$parts) {
        return '未取得';
    }
    return implode(' / ', $parts);
}

function boat_forecast_viewer_format_decimal($value, $digits) {
    if ($value === null || $value === '' || $value === '—' || $value === '-') {
        return (string) $value;
    }
    if (!is_numeric($value)) {
        return (string) $value;
    }
    return number_format((float) $value, (int) $digits, '.', '');
}

function boat_forecast_viewer_sort_rows_by_waku($rows) {
    if (!is_array($rows)) {
        return [];
    }
    usort($rows, function ($a, $b) {
        $waku_a = isset($a['waku']) ? (int) $a['waku'] : 99;
        $waku_b = isset($b['waku']) ? (int) $b['waku'] : 99;
        if ($waku_a === $waku_b) {
            $rank_a = isset($a['rank']) ? (int) $a['rank'] : 99;
            $rank_b = isset($b['rank']) ? (int) $b['rank'] : 99;
            return $rank_a <=> $rank_b;
        }
        return $waku_a <=> $waku_b;
    });
    return $rows;
}

function boat_forecast_viewer_pick_waku_stats($row) {
    $stats = isset($row['waku_stats']) && is_array($row['waku_stats']) ? $row['waku_stats'] : [];
    $local = isset($stats['local']) && is_array($stats['local']) ? $stats['local'] : [];
    $global = isset($stats['global']) && is_array($stats['global']) ? $stats['global'] : [];
    if (!empty($local['races']) && (int) $local['races'] >= 3) {
        return ['label' => '当地', 'stats' => $local];
    }
    if (!empty($global['races']) && (int) $global['races'] >= 3) {
        return ['label' => '全国', 'stats' => $global];
    }
    return ['label' => '---', 'stats' => []];
}

/**
 * Phase 1: Common design tokens.
 * Inject this at the top of every <style> block used by render_single / render_archive / render_review.
 * Keeps existing class names intact — just normalizes colors, typography, radius and shadow.
 */
function boat_forecast_viewer_common_root_css() {
    return <<<'CSS'
    :root {
        /* ===== v5.21 redesign tokens (Phase 1) ===== */
        --bfv-bg:          #f0eee9;
        --bfv-surface:     #ffffff;
        --bfv-surface-sub: #f6f4ef;
        --bfv-ink:         #1a1915;
        --bfv-ink-sub:     #5a5750;
        --bfv-muted:       #8a8680;
        --bfv-line:        rgba(26,25,21,0.10);
        --bfv-line-strong: rgba(26,25,21,0.18);
        --bfv-accent:      #b5542a;      /* warm brick */
        --bfv-accent-soft: #f6e6db;
        --bfv-good:        #1e7b65;
        --bfv-good-soft:   #e6f6f2;
        --bfv-warn:        #b22323;
        --bfv-warn-soft:   #fdf3f3;
        --bfv-hero-ink:    #1a1915;      /* hero dark bg (warm near-black) */
        --bfv-radius-sm:   8px;
        --bfv-radius-md:   12px;
        --bfv-radius-lg:   16px;
        --bfv-shadow-xs:   0 1px 0 rgba(26,25,21,0.04);
        --bfv-shadow-sm:   0 1px 2px rgba(26,25,21,0.06), 0 1px 1px rgba(26,25,21,0.04);
        --bfv-shadow-md:   0 4px 12px rgba(26,25,21,0.06), 0 1px 2px rgba(26,25,21,0.04);
        --bfv-font-sans:   "IBM Plex Sans JP","Noto Sans JP","Hiragino Sans","Hiragino Kaku Gothic ProN","Helvetica Neue",Arial,Meiryo,sans-serif;
        --bfv-font-mono:   "IBM Plex Mono","JetBrains Mono",SFMono-Regular,Consolas,Menlo,monospace;

        /* Phase 7+ handoff naming aliases (map to Phase 1 tokens) */
        --bfv-border:      var(--bfv-line);
        --bfv-border-soft: rgba(26,25,21,0.04);
        --bfv-ink-dim:     var(--bfv-muted);
        --bfv-surface-2:   var(--bfv-surface-sub);
        --bfv-ok:          var(--bfv-good);
        --bfv-ok-soft:     var(--bfv-good-soft);
    }
    @media (prefers-reduced-motion: no-preference) {
        html { scroll-behavior: smooth; }
    }
CSS;
}

/**
 * Phase 1: Web font links (IBM Plex Sans JP / IBM Plex Mono from Google Fonts).
 * Output this inside <head>, before <style>, in render_single / render_archive / render_review.
 */
function boat_forecast_viewer_font_links() {
    return <<<HTML
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+JP:wght@400;500;600;700&display=swap">
HTML;
}

function boat_forecast_viewer_render_nav($active = '') {
    $archive_url = esc_url(get_post_type_archive_link('forecast_day') ?: home_url('/race/'));
    $review_url  = esc_url(home_url('/review/'));
    $a_archive   = $active === 'archive' ? ' bfv-gnav-active' : '';
    $a_review    = $active === 'review'  ? ' bfv-gnav-active' : '';
    echo '<nav class="bfv-gnav">';
    echo '<a class="bfv-gnav-link' . $a_archive . '" href="' . $archive_url . '">🏁 予想一覧</a>';
    echo '<a class="bfv-gnav-link' . $a_review  . '" href="' . $review_url  . '">📊 振り返り</a>';
    echo '</nav>';
}

function boat_forecast_viewer_render_single($payload, $post) {
    $venue = isset($payload['venue_name']) && $payload['venue_name'] !== '' ? $payload['venue_name'] : get_post_meta($post->ID, 'venue_name', true);
    if ($venue === '') {
        $venue = get_the_title($post);
    }
    $date = isset($payload['date']) ? $payload['date'] : get_post_meta($post->ID, 'race_date', true);
    $updated = isset($payload['updated_at']) ? $payload['updated_at'] : get_post_meta($post->ID, 'updated_at', true);
    $status_note = get_post_meta($post->ID, 'status_note', true) ?: '';
    $has_exhibition = !empty($payload['has_exhibition']);
    $has_odds = !empty($payload['has_odds']);
    $races = isset($payload['races']) && is_array($payload['races']) ? $payload['races'] : [];
    ?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?php echo esc_html(get_the_title($post)); ?></title>
<?php echo boat_forecast_viewer_font_links(); ?>
    <style>
<?php echo boat_forecast_viewer_common_root_css(); ?>
        *, *::before, *::after { box-sizing: border-box; }
        :root {
            --bg: #f5f8fa;
            --panel: #ffffff;
            --ink: #08131a;
            --muted: #5a656b;
            --line: rgba(8,19,26,0.14);
            --accent: #1e7b65;
            --accent-soft: #e6f6f2;
            --warn: #b22323;
            --warn-soft: #fdf3f3;
            --good: #1e7b65;
            --good-soft: #e6f6f2;
            --shadow: 0px 1px 3px 1px rgba(0,0,0,0.14), 0px 1px 2px 0px rgba(0,0,0,0.22);
            --note-green: #5ac8b8;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            color: var(--ink);
            background: var(--bfv-bg);
            font-family: var(--bfv-font-sans);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        a { color: inherit; }
        .bfv-shell {
            width: min(1120px, calc(100% - 24px));
            margin: 0 auto;
            padding: 24px 0 56px;
            overflow-x: visible;
        }
        /* ===== Phase 10: single hero & side info ===== */
        .bfv-hero {
            padding: 20px 24px 22px;
            border-radius: var(--bfv-radius-lg);
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-border);
            display: grid;
            gap: 10px;
            position: relative;
            overflow: hidden;
        }
        .bfv-hero::after {
            content: "";
            position: absolute;
            inset: auto -60px -60px auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: var(--bfv-accent-soft);
            opacity: .5;
            pointer-events: none;
        }
        .bfv-kicker {
            display: inline-block;
            font-size: 11px;
            letter-spacing: 0.12em;
            color: var(--bfv-accent);
            font-weight: 600;
            padding: 0;
            background: transparent;
            border: 0;
            text-transform: uppercase;
        }
        .bfv-title {
            margin: 0;
            font-size: clamp(24px, 3.2vw, 34px);
            font-weight: 800;
            line-height: 1.15;
            color: var(--bfv-ink);
            letter-spacing: 0.02em;
            font-feature-settings: "palt";
        }
        .bfv-title span {
            display: inline-block;
            margin-left: 10px;
            font-size: 0.6em;
            color: var(--bfv-ink-dim);
            font-weight: 600;
        }
        .bfv-sub {
            margin: 0;
            font-size: 13px;
            color: var(--bfv-ink-dim);
            max-width: 60ch;
            line-height: 1.6;
        }
        .bfv-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px 10px;
            align-items: center;
        }
        .bfv-jump {
            margin-left: auto;
            font-size: 12px;
            font-weight: 600;
            color: var(--bfv-accent);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 120ms ease;
            padding: 0;
            background: transparent;
            border-radius: 0;
        }
        .bfv-jump:hover {
            border-bottom-color: var(--bfv-accent);
            background: transparent;
            text-decoration: none;
        }
        .bfv-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
            color: var(--bfv-ink-dim);
            border: 1px solid var(--bfv-border);
            background: var(--bfv-surface-2);
        }
        .bfv-badge.is-on {
            color: var(--bfv-ok);
            border-color: transparent;
            background: var(--bfv-ok-soft);
        }
        .bfv-badge.is-on::before {
            content: "●";
            font-size: 8px;
            line-height: 1;
        }
        .bfv-note {
            margin-top: 14px;
            padding: 10px 12px;
            border-radius: var(--bfv-radius-sm);
            background: var(--bfv-warn-soft);
            color: var(--bfv-warn);
            font-size: 12.5px;
            line-height: 1.5;
        }
        .bfv-grid {
            display: grid;
            grid-template-columns: minmax(0, 1fr) 320px;
            gap: 16px;
            margin-top: 16px;
        }
        @media (max-width: 960px) {
            .bfv-grid { grid-template-columns: 1fr; }
        }
        .bfv-grid > * { min-width: 0; }
        .bfv-panel {
            padding: 18px 20px;
            border-radius: var(--bfv-radius-lg);
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-border);
            display: grid;
            gap: 12px;
            width: 100%;
            max-width: 100%;
        }
        .bfv-panel-head {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            padding: 0;
            border-bottom: 0;
        }
        .bfv-panel-head h2 {
            margin: 0 0 2px;
            font-size: 14px;
            font-weight: 700;
            color: var(--bfv-ink);
            letter-spacing: 0.02em;
            font-feature-settings: "palt";
        }
        .bfv-panel-head p {
            margin: 0;
            font-size: 12px;
            color: var(--bfv-ink-dim);
        }
        .bfv-info-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }
        .bfv-info-card {
            padding: 10px 12px;
            border-radius: var(--bfv-radius-sm);
            background: var(--bfv-surface-2);
            display: grid;
            gap: 3px;
        }
        .bfv-info-card strong {
            font-size: 10px;
            letter-spacing: 0.08em;
            color: var(--bfv-ink-dim);
            font-weight: 600;
            text-transform: uppercase;
        }
        .bfv-info-card span {
            font-size: 13px;
            color: var(--bfv-ink);
            font-variant-numeric: tabular-nums;
            word-break: break-all;
        }
        /* ===== Phase 8: 12R summary table ===== */
        .bfv-table-wrap {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: var(--bfv-radius-md);
            border: 1px solid var(--bfv-border);
            background: var(--bfv-surface);
        }
        .bfv-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .bfv-table thead { background: var(--bfv-surface-2); }
        .bfv-table th {
            text-align: left;
            padding: 10px 12px;
            font-size: 11px;
            letter-spacing: 0.06em;
            color: var(--bfv-ink-dim);
            font-weight: 600;
            border-bottom: 1px solid var(--bfv-border);
            white-space: nowrap;
        }
        .bfv-table td {
            padding: 12px;
            border-bottom: 1px solid var(--bfv-border-soft);
            vertical-align: top;
        }
        .bfv-table tr:last-child td { border-bottom: none; }
        .bfv-table tr:hover td { background: var(--bfv-surface-2); }

        /* R column as pill button */
        .bfv-race-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 40px;
            height: 32px;
            border-radius: var(--bfv-radius-sm);
            background: var(--bfv-accent-soft);
            color: var(--bfv-accent);
            font-weight: 700;
            font-size: 14px;
            text-decoration: none;
            transition: background 120ms ease, color 120ms ease;
        }
        .bfv-race-link:hover {
            background: var(--bfv-accent);
            color: var(--bfv-surface);
            text-decoration: none;
        }

        /* bet text inside summary table */
        .bfv-bet {
            font-weight: 800;
            font-family: SFMono-Regular, Consolas, Menlo, Courier, monospace;
            font-size: 15px;
        }
        .bfv-bet-list { display: grid; gap: 6px; }
        .bfv-table-bets {
            display: flex;
            flex-wrap: wrap;
            gap: 4px 8px;
            min-width: 88px;
        }
        .bfv-table-bets .bfv-bet {
            font-size: 12px;
            font-weight: 600;
            color: var(--bfv-ink);
            background: transparent;
            padding: 0;
            line-height: 1.25;
        }
        .bfv-table-bets .bfv-odds {
            font-size: 11px;
            color: var(--bfv-ink-dim);
            margin-left: 2px;
        }

        /* confidence dot (Phase 8d) */
        .bfv-table td[data-conf] {
            position: relative;
            padding-right: 24px;
            font-variant-numeric: tabular-nums;
            font-weight: 600;
        }
        .bfv-table td[data-conf]::after {
            content: "";
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--bfv-ink-dim);
        }
        .bfv-table td[data-conf="high"]::after { background: var(--bfv-ok); }
        .bfv-table td[data-conf="mid"]::after  { background: var(--bfv-accent); }
        .bfv-table td[data-conf="low"]::after  { background: var(--bfv-warn); }
        /* confidence text color (for summary table td etc.) */
        .is-conf-high { color: var(--bfv-ok); }
        .is-conf-mid { color: var(--bfv-accent); }
        .is-conf-low { color: var(--bfv-warn); }
        /* confidence pill variants (Phase 7) */
        .bfv-pill.is-conf-high { color: var(--bfv-ok); background: var(--bfv-ok-soft); }
        .bfv-pill.is-conf-mid  { color: var(--bfv-accent); background: var(--bfv-accent-soft); }
        .bfv-pill.is-conf-low  { color: var(--bfv-warn); background: var(--bfv-warn-soft); }
        .bfv-rough {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            background: var(--bfv-warn-soft);
            color: var(--bfv-warn);
            font-size: 11px;
            font-weight: 600;
        }
        .bfv-legend {
            display: grid;
            gap: 12px;
            padding: 18px 20px 20px;
        }
        .bfv-legend dl {
            margin: 0;
            display: grid;
            grid-template-columns: 84px 1fr;
            gap: 6px 10px;
            font-size: 14px;
        }
        .bfv-legend dt { color: var(--muted); }
        .bfv-races {
            display: grid;
            gap: 14px;
            margin-top: 18px;
        }
        /* ===== Phase 7: race card ===== */
        .bfv-card {
            padding: 18px 20px;
            border-radius: var(--bfv-radius-lg);
            border: 1px solid var(--bfv-border);
            background: var(--bfv-surface);
            box-shadow: var(--bfv-shadow-xs);
            display: grid;
            gap: 14px;
            width: 100%;
            max-width: 100%;
        }
        /* grid child が overflow-x: auto 子孫を持つ場合に shrink を許可 */
        .bfv-card > * { min-width: 0; }
        .bfv-card + .bfv-card { margin-top: 14px; }
        .bfv-card-head {
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 0;
        }
        .bfv-card-head h3 {
            margin: 0;
            font-size: 28px;
            font-weight: 800;
            line-height: 1;
        }
        .bfv-card-sub {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            color: var(--bfv-ink-dim);
            font-size: 13px;
        }
        .bfv-pill {
            display: inline-flex;
            align-items: center;
            padding: 5px 10px;
            border-radius: 999px;
            background: var(--bfv-surface-2);
            border: 1px solid var(--bfv-border);
            color: var(--bfv-ink-dim);
            font-size: 12px;
            font-weight: 700;
        }
        .bfv-bets {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
        }
        .bfv-betbox {
            padding: 12px 14px;
            border-radius: var(--bfv-radius-md);
            border: 1px solid var(--bfv-border);
            background: var(--bfv-surface-2);
        }
        .bfv-betbox main, .bfv-betbox strong { display: block; }
        .bfv-betbox strong {
            font-size: 11px;
            color: var(--bfv-ink-dim);
            margin-bottom: 6px;
            letter-spacing: .08em;
        }
        .bfv-betbox .bfv-bet { font-size: 20px; }
        .bfv-bet {
            display: inline-flex;
            align-items: baseline;
            gap: 4px;
            font-variant-numeric: tabular-nums;
            font-weight: 600;
        }
        .bfv-odds {
            font-size: 11px;
            color: var(--bfv-ink-dim);
            font-weight: 500;
            margin-left: 4px;
        }
        .bfv-betbox.is-main {
            background: var(--bfv-accent-soft);
            border-color: var(--bfv-accent);
        }
        .bfv-betbox.is-main strong { color: var(--bfv-accent); }
        .bfv-comment {
            padding: 10px 12px;
            background: var(--bfv-surface-2);
            border-left: 3px solid var(--bfv-accent);
            border-radius: var(--bfv-radius-sm);
            font-size: 13px;
            color: var(--bfv-ink);
        }
        .bfv-reason-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
        @media (max-width: 640px) {
            .bfv-reason-grid { grid-template-columns: 1fr; }
        }
        .bfv-reason {
            padding: 10px 12px;
            border-radius: var(--bfv-radius-sm);
            background: var(--bfv-surface-2);
            font-size: 12.5px;
            line-height: 1.55;
            color: var(--bfv-ink);
        }
        .bfv-reason strong {
            display: block;
            font-size: 11px;
            color: var(--bfv-ink-dim);
            margin-bottom: 3px;
            letter-spacing: .05em;
        }
        .bfv-picks {
            margin-top: 14px;
            display: grid;
            gap: 10px;
        }
        .bfv-pick {
            display: grid;
            grid-template-columns: 28px minmax(0, 1fr) auto;
            gap: 10px;
            align-items: center;
            padding: 12px 14px;
            border-radius: 12px;
            background: var(--panel);
            border: 1px solid var(--line);
        }
        .bfv-pick-mark {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 28px;
            min-width: 28px;
            background: transparent;
            color: var(--bfv-accent);
            font-weight: 800;
            font-size: 28px;
            line-height: 1;
        }
        .bfv-pick-mark.is-plain {
            color: transparent;
        }
        .bfv-waku-name-cell {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .bfv-waku-chip {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 20px;
            height: 20px;
            border: 1px solid #ccc;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            line-height: 1;
            flex: 0 0 20px;
        }
        .bfv-waku-name {
            font-weight: 700;
        }
        .bfv-pick-name {
            font-size: 15px;
            font-weight: 700;
        }
        .bfv-female {
            color: #d72662;
            font-weight: 800;
            margin-right: 4px;
        }
        .bfv-pick-meta {
            color: var(--muted);
            font-size: 13px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 3px;
        }
        .bfv-grade { font-weight: 800; }
        .bfv-grade.grade-a1, .bfv-grade.grade-a2 { color: #c62828; }
        .bfv-grade.grade-b { color: #1565c0; }
        .bfv-pick-note {
            color: var(--muted);
            font-size: 13px;
            margin-top: 6px;
        }
        .bfv-score {
            text-align: right;
            font-family: SFMono-Regular, Consolas, Menlo, Courier, monospace;
            color: var(--accent);
            font-weight: 800;
            white-space: nowrap;
        }
        .bfv-foot {
            margin-top: 18px;
            color: var(--muted);
            font-size: 13px;
        }
        .bfv-review {
            margin-top: 20px;
            padding: 18px;
            border-radius: 12px;
            background: #08131a;
            color: #fff;
            box-shadow: var(--shadow);
            width: 100%;
            max-width: 100%;
            min-width: 0;
            overflow: hidden;
        }
        .bfv-review-head {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            min-width: 0;
        }
        .bfv-review-head > div { min-width: 0; }
        .bfv-review h3 {
            margin: 0 0 10px;
            font-size: 20px;
        }
        .bfv-review-meta {
            color: rgba(255,255,255,.78);
            font-size: 13px;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .bfv-review-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 12px;
            min-width: 0;
        }
        .bfv-review-card {
            background: rgba(255,255,255,.1);
            border-radius: 16px;
            padding: 12px;
            min-width: 0;
        }
        .bfv-review-card.is-primary {
            background: rgba(255,255,255,.18);
            border: 1px solid rgba(255,255,255,.2);
        }
        .bfv-review-sub {
            font-size: 10px;
            color: rgba(255,255,255,.5);
            margin-top: 4px;
        }
        .bfv-review-card strong {
            display: block;
            font-size: 11px;
            letter-spacing: .06em;
            text-transform: uppercase;
            color: rgba(255,255,255,.7);
            margin-bottom: 6px;
        }
        .bfv-review-value {
            font-size: 22px;
            font-weight: 800;
        }
        .bfv-review-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            border-radius: 999px;
            background: rgba(255,255,255,.12);
            color: #fff;
            text-decoration: none;
            font-size: 13px;
            font-weight: 700;
        }
        .bfv-review-link:hover { text-decoration: underline; }
        .bfv-review-blocks {
            display: grid;
            gap: 16px;
            margin-top: 16px;
            min-width: 0;
        }
        .bfv-review-block { min-width: 0; }
        .bfv-review-block h4 {
            margin: 0 0 8px;
            font-size: 15px;
            color: #fff;
        }
        .bfv-review-list {
            margin: 0;
            padding-left: 18px;
            color: rgba(255,255,255,.84);
            min-width: 0;
        }
        .bfv-review-list li {
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .bfv-review-list li + li { margin-top: 6px; }
        .bfv-review-races {
            display: grid;
            gap: 8px;
            min-width: 0;
        }
        .bfv-review-race {
            padding: 10px 12px;
            border-radius: 14px;
            background: rgba(255,255,255,.10);
            border: 1px solid rgba(255,255,255,.14);
            color: rgba(255,255,255,.92);
            font-size: 13px;
            line-height: 1.5;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .bfv-review-table-wrap {
            min-width: 0;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .bfv-review-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 860px;
            font-size: 12px;
        }
        .bfv-review-table th,
        .bfv-review-table td {
            padding: 7px 9px;
            border: 1px solid rgba(255,255,255,.16);
            text-align: left;
            vertical-align: top;
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        .bfv-review-table th {
            background: rgba(255,255,255,.12);
            color: rgba(255,255,255,.88);
        }
        .bfv-review-table tr:nth-child(even) td {
            background: rgba(255,255,255,.05);
        }
        .bfv-review-table th:first-child,
        .bfv-review-table td:first-child {
            min-width: 56px;
            white-space: nowrap;
        }
        .bfv-review-table th:last-child,
        .bfv-review-table td:last-child {
            min-width: 180px;
        }
        /* v5.18: 判定マーク色分け */
        .verdict-hit { color: #1f7a4d; font-weight: 700; }
        .verdict-order { color: #1565c0; font-weight: 700; }
        .verdict-box { color: #916626; }
        .verdict-miss { color: rgba(255,255,255,.4); }
        /* ===== Phase 9: 予算 / 展示 / コメント統一 ===== */
        /* コメント実データ判定マーク */
        .bfv-comment-table .cmt-good    { color: var(--bfv-ok); font-weight: 700; }
        .bfv-comment-table .cmt-bad     { color: var(--bfv-warn); font-weight: 700; }
        .bfv-comment-table .cmt-neutral { color: var(--bfv-ink-dim); }
        .bfv-cmt-keywords {
            margin-top: 3px;
            font-size: 11px;
            color: var(--bfv-ink-dim);
        }
        /* 展示実データ評価マーク */
        .bfv-detail-table .ex-best { color: var(--bfv-accent); font-weight: 700; }
        .bfv-detail-table .ex-good { color: var(--bfv-ok); font-weight: 600; }
        .bfv-detail-table .ex-slow { color: var(--bfv-warn); font-weight: 600; }
        .bfv-exhibition-order { margin-top: 8px; font-size: 12px; color: var(--bfv-ink-dim); }

        /* 予算別買い目 */
        .bfv-budget-section { display: grid; gap: 10px; margin-top: 12px; }
        .bfv-budget-section h4 {
            margin: 0;
            font-size: 12px;
            letter-spacing: 0.08em;
            color: var(--bfv-accent);
            font-weight: 600;
        }
        .bfv-budget-box {
            padding: 12px 14px;
            border-radius: var(--bfv-radius-md);
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-border-soft);
        }
        .bfv-budget-head {
            display: flex;
            flex-wrap: wrap;
            align-items: baseline;
            gap: 6px 10px;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--bfv-ink);
        }
        .bfv-budget-status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 600;
        }
        .bfv-budget-ok { color: var(--bfv-ok); background: var(--bfv-ok-soft); }
        .bfv-budget-ng { color: var(--bfv-warn); background: var(--bfv-warn-soft); }
        .bfv-budget-note { font-size: 12px; color: var(--bfv-ink-dim); }
        .bfv-budget-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12.5px;
        }
        .bfv-budget-table th,
        .bfv-budget-table td {
            padding: 6px 8px;
            border-bottom: 1px solid var(--bfv-border-soft);
            text-align: left;
            font-variant-numeric: tabular-nums;
        }
        .bfv-budget-table th {
            background: var(--bfv-surface-2);
            font-size: 11px;
            color: var(--bfv-ink-dim);
            font-weight: 600;
        }
        .bfv-budget-table tr:last-child td { border-bottom: none; }
        /* v5.18: review 追加カード行 */
        .bfv-review-grid-extra { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 10px; }
        .bfv-review-info { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; font-size: 13px; color: rgba(255,255,255,.7); }
        .bfv-review-upsets { margin-top: 6px; font-size: 12px; color: rgba(255,255,255,.6); }
        .bfv-review-upsets li { margin-top: 2px; }
        .bfv-detail-block {
            margin-top: 4px;
            padding: 14px 16px;
            border-radius: var(--bfv-radius-md);
            background: var(--bfv-surface-2);
            border: 1px solid var(--bfv-border-soft);
        }
        .bfv-detail-block h4 {
            margin: 0 0 10px;
            font-size: 12px;
            letter-spacing: 0.08em;
            color: var(--bfv-ink-dim);
            font-weight: 600;
        }
        .bfv-detail-wrap {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            border-radius: var(--bfv-radius-sm);
            border: 1px solid var(--bfv-border-soft);
            background: var(--bfv-surface);
        }
        .bfv-detail-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 820px;
            font-size: 12.5px;
        }
        .bfv-detail-table th {
            background: var(--bfv-surface-2);
            text-align: left;
            padding: 8px 10px;
            font-size: 11px;
            color: var(--bfv-ink-dim);
            font-weight: 600;
            border-bottom: 1px solid var(--bfv-border-soft);
            white-space: nowrap;
        }
        .bfv-detail-table td {
            padding: 8px 10px;
            border-bottom: 1px solid var(--bfv-border-soft);
            font-variant-numeric: tabular-nums;
            vertical-align: top;
        }
        .bfv-detail-table tr:last-child td { border-bottom: none; }
        .bfv-rank-cell {
            font-weight: 800;
            white-space: nowrap;
        }
        .bfv-dim {
            color: var(--muted);
        }
        .bfv-meter {
            display: inline-flex;
            width: 72px;
            height: 7px;
            border-radius: 999px;
            overflow: hidden;
            background: #dce0e3;
            vertical-align: middle;
            margin-left: 6px;
        }
        .bfv-meter-fill {
            display: block;
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #1e7b65, #5ac8b8);
        }
        .bfv-meter.rank2 .bfv-meter-fill { background: linear-gradient(90deg, #5a656b, #9ca7ad); }
        .bfv-meter.rank3 .bfv-meter-fill { background: linear-gradient(90deg, #7e888f, #c5ccd1); }
        .bfv-meter.top3 .bfv-meter-fill { background: linear-gradient(90deg, #1e7b65, #5ac8b8); }
        .bfv-meter.score .bfv-meter-fill { background: linear-gradient(90deg, #1e7b65, #5ac8b8); }
        .sticky-name-table th:nth-child(1),
        .sticky-name-table td:nth-child(1) {
            position: sticky;
            left: 0;
            z-index: 3;
            min-width: 100px;
            max-width: 140px;
        }
        .sticky-score-table th:nth-child(1),
        .sticky-score-table td:nth-child(1) {
            position: sticky;
            left: 0;
            z-index: 4;
            min-width: 100px;
            max-width: 140px;
        }
        .sticky-name-table td:nth-child(1),
        .sticky-score-table td:nth-child(1) {
            background: var(--bfv-surface);
            box-shadow: 1px 0 0 var(--bfv-border-soft);
        }
        .sticky-name-table th:nth-child(1),
        .sticky-score-table th:nth-child(1) {
            background: var(--bfv-surface-2);
            z-index: 5;
        }
        /* sticky 1列目内: [マーク + 枠番] を1行目に固定、選手名を2行目に折返し */
        .sticky-name-table td:nth-child(1),
        .sticky-score-table td:nth-child(1) {
            line-height: 1.35;
        }
        .bfv-rank-mark {
            display: inline-block;
            margin-right: 4px;
            font-size: inherit;
            font-weight: 800;
            color: var(--bfv-accent);
            line-height: 1;
            vertical-align: middle;
        }
        /* waku-name-cell を inline-flex + flex-wrap にして、chip を1行目・
           name を flex-basis: 100% で強制2行目へ */
        .sticky-name-table td:nth-child(1) .bfv-waku-name-cell,
        .sticky-score-table td:nth-child(1) .bfv-waku-name-cell {
            display: inline-flex;
            flex-wrap: wrap;
            align-items: center;
            column-gap: 4px;
            row-gap: 2px;
            vertical-align: middle;
            max-width: 100%;
        }
        .sticky-name-table td:nth-child(1) .bfv-waku-chip,
        .sticky-score-table td:nth-child(1) .bfv-waku-chip {
            flex: 0 0 auto;
        }
        .sticky-name-table td:nth-child(1) .bfv-waku-name,
        .sticky-score-table td:nth-child(1) .bfv-waku-name {
            flex: 0 0 100%;
            display: block;
            word-break: break-all;
            overflow-wrap: anywhere;
            font-size: inherit;
        }
        @media (max-width: 960px) {
            .bfv-grid { grid-template-columns: 1fr; }
            .bfv-bets { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 640px) {
            .bfv-shell { width: min(100% - 16px, 100%); padding-top: 12px; }
            .bfv-hero { border-radius: 12px; padding: 20px; }
            .bfv-title { font-size: clamp(24px, 9vw, 32px); }
            .bfv-sub { font-size: 13px; line-height: 1.65; }
            .bfv-panel, .bfv-card { border-radius: 12px; }
            .bfv-review { padding: 14px; border-radius: 12px; }
            .bfv-bets { grid-template-columns: 1fr; }
            .bfv-reason-grid { grid-template-columns: 1fr; }
            .bfv-info-grid { grid-template-columns: 1fr; }
            .bfv-pick {
                grid-template-columns: 22px minmax(0, 1fr);
                align-items: start;
            }
            .bfv-pick-mark {
                width: 22px;
                min-width: 22px;
                font-size: 22px;
                margin-top: 2px;
            }
            .bfv-score { text-align: left; }
            .bfv-card-head h3 { font-size: 22px; }
            .bfv-table { min-width: 560px; }
            .bfv-table th:nth-child(4),
            .bfv-table td:nth-child(4),
            .bfv-table th:nth-child(5),
            .bfv-table td:nth-child(5),
            .bfv-table th:nth-child(7),
            .bfv-table td:nth-child(7) {
                display: none;
            }
            .bfv-review-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .bfv-review-sub { font-size: 9px; }
            .bfv-review-table { min-width: 760px; }
            .bfv-review-table-wrap {
                margin-inline: -6px;
                padding-bottom: 4px;
            }
            .bfv-review-table th,
            .bfv-review-table td {
                font-size: 11px;
                padding: 6px 7px;
            }
            /* v5.20: スマホ版改善 */
            /* 1) 選手名（艇）列を可能な限り狭める → 他情報の表示幅確保 */
            .sticky-name-table th:nth-child(1),
            .sticky-name-table td:nth-child(1) {
                min-width: 52px !important;
                max-width: 64px;
                font-size: 11px;
                padding: 4px 5px;
                line-height: 1.25;
                word-break: break-all;
            }
            /* 2) コメント実データ本文のテキストサイズ縮小 */
            .bfv-comment {
                font-size: 11px;
                padding: 10px 12px;
                line-height: 1.45;
            }
            .bfv-detail-table td .bfv-dim,
            .bfv-detail-table td div.bfv-dim {
                font-size: 10px;
                line-height: 1.35;
            }
            /* コメント実データテーブルのセル全体を小さく（コメント本文が裸テキストのため） */
            .bfv-comment-table th,
            .bfv-comment-table td {
                font-size: 10.5px !important;
                line-height: 1.4;
                padding: 5px 6px;
            }
            .bfv-comment-table td:nth-child(3) {
                white-space: normal;
                word-break: break-word;
            }
        }
        /* ===== グローバルナビ（v5.20: 上部固定） ===== */
        .bfv-gnav {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
            margin-bottom: 14px;
            padding: 8px 12px;
            background: rgba(255,255,255,.92);
            border: 1px solid var(--line);
            border-radius: 999px;
            backdrop-filter: blur(10px);
            position: sticky;
            top: 8px;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(8,19,26,.08);
        }
        .bfv-gnav-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            color: var(--accent);
            text-decoration: none;
            transition: background .15s, color .15s;
        }
        .bfv-gnav-link:hover { background: rgba(8,19,26,.06); text-decoration: none; }
        .bfv-gnav-active { background: #08131a !important; color: #fff !important; }
        /* ===== カード内「早見表へ戻る」 ===== */
        .bfv-card-foot {
            display: flex;
            justify-content: flex-end;
            padding: 10px 20px 14px;
            border-top: 1px solid rgba(8,19,26,0.14);
            margin-top: 8px;
        }
        .bfv-back-btn {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            color: var(--muted);
            background: rgba(8,19,26,.06);
            text-decoration: none;
            transition: background .15s;
        }
        .bfv-back-btn:hover { background: rgba(8,19,26,.10); text-decoration: none; }
    </style>
</head>
<body>
<div class="bfv-shell">
    <?php boat_forecast_viewer_render_nav(); ?>
    <section class="bfv-hero">
        <span class="bfv-kicker">ボートレース予想</span>
        <h1 class="bfv-title"><?php echo esc_html($venue); ?> <span><?php echo esc_html($date); ?></span></h1>
        <p class="bfv-sub">開催日ごとの予想ページです。展示・オッズの反映状況に応じて、同じURLのまま内容を更新します。</p>
        <div class="bfv-meta">
            <?php echo boat_forecast_viewer_render_badge($has_exhibition, '展示'); ?>
            <?php echo boat_forecast_viewer_render_badge($has_odds, 'オッズ'); ?>
            <span class="bfv-badge"><?php echo esc_html('最終更新: ' . $updated); ?></span>
            <?php if (!empty($payload['review_summary'])) : ?>
                <a class="bfv-jump" href="#review">振り返りへ</a>
            <?php endif; ?>
        </div>
        <?php if ($status_note) : ?>
            <div class="bfv-note"><?php echo esc_html($status_note); ?></div>
        <?php endif; ?>
    </section>

    <section class="bfv-grid">
        <div class="bfv-panel" id="bfv-summary">
            <div class="bfv-panel-head">
                <div>
                    <h2>12R 早見表</h2>
                    <p>PCは一覧比較向け、スマホは本線中心の簡略表示です。詳しくは各レースカードで確認できます。</p>
                </div>
            </div>
            <div class="bfv-table-wrap">
                <table class="bfv-table">
                    <thead>
                        <tr>
                            <th>R</th>
                            <th>発走</th>
                            <th>本線</th>
                            <th>対抗</th>
                            <th>穴</th>
                            <th>信頼</th>
                            <th>備考</th>
                        </tr>
                    </thead>
                    <tbody>
                    <?php foreach ($races as $race) : ?>
                        <tr>
                            <td><a class="bfv-race-link" href="#race-<?php echo esc_attr((string) ($race['race_no'] ?? '')); ?>"><?php echo esc_html((string) ($race['race_no'] ?? '')); ?>R</a></td>
                            <td><?php echo esc_html((string) ($race['start_time'] ?? '')); ?></td>
                            <td>
                                <div class="bfv-table-bets">
                                    <?php foreach ((isset($race['main_bets']) && is_array($race['main_bets']) ? $race['main_bets'] : [['combo' => ($race['main_bet'] ?? '')]]) as $bet) : ?>
                                        <?php if (!empty($bet['combo'])) : ?>
                                            <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                        <?php endif; ?>
                                    <?php endforeach; ?>
                                </div>
                            </td>
                            <td>
                                <div class="bfv-table-bets">
                                    <?php foreach ((isset($race['sub_bets']) && is_array($race['sub_bets']) ? $race['sub_bets'] : [['combo' => ($race['sub_bet'] ?? '')]]) as $bet) : ?>
                                        <?php if (!empty($bet['combo'])) : ?>
                                            <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                        <?php endif; ?>
                                    <?php endforeach; ?>
                                </div>
                            </td>
                            <td>
                                <div class="bfv-table-bets">
                                    <?php foreach ((isset($race['longshot_bets']) && is_array($race['longshot_bets']) ? $race['longshot_bets'] : [['combo' => ($race['longshot_bet'] ?? '')]]) as $bet) : ?>
                                        <?php if (!empty($bet['combo'])) : ?>
                                            <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                        <?php endif; ?>
                                    <?php endforeach; ?>
                                </div>
                            </td>
                            <td class="<?php echo esc_attr(boat_forecast_viewer_conf_class((string) ($race['confidence_label'] ?? 'low'))); ?>" data-conf="<?php echo esc_attr((string) ($race['confidence_label'] ?? 'low')); ?>">
                                <?php echo esc_html((string) ($race['confidence'] ?? '')); ?>%
                            </td>
                            <td>
                                <?php if (!empty($race['is_rough'])) : ?>
                                    <span class="bfv-rough">荒れ注意</span>
                                <?php endif; ?>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        </div>

        <aside class="bfv-panel">
            <div class="bfv-panel-head">
                <div>
                    <h2>ページ情報</h2>
                    <p>公開状態の要点</p>
                </div>
            </div>
            <div class="bfv-legend">
                <div class="bfv-info-grid">
                    <div class="bfv-info-card">
                        <strong>更新段階</strong>
                        <span><?php echo esc_html((string) get_post_meta($post->ID, 'publish_stage', true)); ?></span>
                    </div>
                    <div class="bfv-info-card">
                        <strong>会場コード</strong>
                        <span><?php echo esc_html((string) get_post_meta($post->ID, 'venue_code', true)); ?></span>
                    </div>
                    <div class="bfv-info-card">
                        <strong>表示件数</strong>
                        <span><?php echo esc_html((string) count($races)); ?>R</span>
                    </div>
                    <div class="bfv-info-card">
                        <strong>スラッグ</strong>
                        <span><?php echo esc_html($post->post_name); ?></span>
                    </div>
                </div>
            </div>
        </aside>
    </section>

    <section class="bfv-races">
        <?php foreach ($races as $race) : ?>
            <article class="bfv-card" id="race-<?php echo esc_attr((string) ($race['race_no'] ?? '')); ?>">
                <div class="bfv-card-head">
                    <div>
                        <h3><?php echo esc_html((string) ($race['race_no'] ?? '')); ?>R</h3>
                    <div class="bfv-card-sub">
                        <span><?php echo esc_html((string) ($race['start_time'] ?? '')); ?></span>
                        <?php if (!empty($race['race_type'])) : ?>
                            <span><?php echo esc_html((string) $race['race_type']); ?></span>
                        <?php endif; ?>
                        <?php if (!empty($race['tide_status'])) : ?>
                            <span><?php echo esc_html((string) $race['tide_status']); ?></span>
                        <?php endif; ?>
                    </div>
                </div>
                    <div class="bfv-card-sub">
                        <span class="bfv-pill <?php echo esc_attr(boat_forecast_viewer_conf_class((string) ($race['confidence_label'] ?? 'low'))); ?>">
                            信頼度 <?php echo esc_html((string) ($race['confidence'] ?? '')); ?>%
                        </span>
                        <?php if (!empty($race['is_rough'])) : ?>
                            <span class="bfv-pill" style="color: var(--warn); background: var(--warn-soft);">荒れ注意</span>
                        <?php endif; ?>
                        <span class="bfv-pill"><?php echo !empty($race['has_exhibition']) ? '展示反映' : '展示未反映'; ?></span>
                        <span class="bfv-pill"><?php echo !empty($race['has_odds']) ? 'オッズ反映' : 'オッズ未反映'; ?></span>
                    </div>
                </div>
                <div class="bfv-bets">
                    <section class="bfv-betbox is-main">
                        <strong>本線</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['main_bets']) && is_array($race['main_bets']) ? $race['main_bets'] : [['combo' => ($race['main_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox">
                        <strong>対抗</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['sub_bets']) && is_array($race['sub_bets']) ? $race['sub_bets'] : [['combo' => ($race['sub_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox">
                        <strong>穴</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['longshot_bets']) && is_array($race['longshot_bets']) ? $race['longshot_bets'] : [['combo' => ($race['longshot_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox">
                        <strong>押さえ</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['cover_bets']) && is_array($race['cover_bets']) ? $race['cover_bets'] : [['combo' => ($race['cover_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds"><?php echo esc_html(number_format((float) $bet['odds'], 1)); ?>倍</span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                </div>
                <?php if (!empty($race['comment'])) : ?>
                    <div class="bfv-comment"><span class="bfv-dim" style="font-size:11px;">本線根拠:</span> <?php echo esc_html((string) $race['comment']); ?></div>
                <?php endif; ?>
                <?php if (!empty($race['bet_reasons']) && is_array($race['bet_reasons'])) : ?>
                    <div class="bfv-reason-grid">
                        <?php foreach ([
                            'main' => '本線理由',
                            'sub' => '対抗理由',
                            'longshot' => '穴理由',
                            'cover' => '押さえ理由',
                        ] as $key => $label) : ?>
                            <?php if (!empty($race['bet_reasons'][$key])) : ?>
                                <section class="bfv-reason">
                                    <strong><?php echo esc_html($label); ?></strong>
                                    <?php echo esc_html((string) $race['bet_reasons'][$key]); ?>
                                </section>
                            <?php endif; ?>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
                <?php /* v5.18: 予算別買い目セクション */ ?>
                <?php if (!empty($race['budget_plans']) && is_array($race['budget_plans'])) : ?>
                    <div class="bfv-budget-section">
                        <h4 style="font-size:14px;color:var(--accent);margin:0 0 6px;">予算別買い目</h4>
                        <?php foreach ($race['budget_plans'] as $plan) : ?>
                            <div class="bfv-budget-box">
                                <div class="bfv-budget-head">
                                    予算 <?php echo esc_html(number_format((int) ($plan['budget'] ?? 0))); ?>円
                                    / <?php echo esc_html((string) ($plan['strategy_name'] ?? '配分案')); ?>
                                    <?php $trig_ok = !empty($plan['no_trigarami']); ?>
                                    <span class="bfv-budget-status <?php echo $trig_ok ? 'bfv-budget-ok' : 'bfv-budget-ng'; ?>"><?php echo $trig_ok ? 'トリガミ回避' : 'トリガミ回避不可'; ?></span>
                                    <span class="bfv-budget-note">最悪収支 <?php echo esc_html(number_format((int) ($plan['min_profit'] ?? 0))); ?>円 / 期待収支 <?php echo esc_html(number_format((int) ($plan['expected_profit'] ?? 0))); ?>円</span>
                                </div>
                                <?php if (!empty($plan['strategy_description'])) : ?>
                                    <div class="bfv-budget-note" style="margin-bottom:6px;"><?php echo esc_html((string) $plan['strategy_description']); ?></div>
                                <?php endif; ?>
                                <?php if (!empty($plan['rows']) && is_array($plan['rows'])) : ?>
                                    <table class="bfv-budget-table">
                                        <tr><th>種別</th><th>買い目</th><th>配分</th><th>オッズ</th><th>的中時収支</th></tr>
                                        <?php foreach ($plan['rows'] as $brow) : ?>
                                            <tr>
                                                <td><?php echo esc_html((string) ($brow['label'] ?? '')); ?></td>
                                                <td><?php echo esc_html((string) ($brow['combo'] ?? '')); ?></td>
                                                <td><?php echo esc_html(number_format((int) ($brow['stake'] ?? 0))); ?>円</td>
                                                <td><?php echo esc_html(number_format((float) ($brow['odds'] ?? 0), 1)); ?>倍</td>
                                                <td><?php echo esc_html(number_format((int) ($brow['profit_if_hit'] ?? 0))); ?>円</td>
                                            </tr>
                                        <?php endforeach; ?>
                                    </table>
                                <?php endif; ?>
                            </div>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>

                <?php /* v5.18: コメント実データセクション（v5.20: 下部の見やすい表示と重複のため非表示） */ ?>
                <?php if (false && !empty($race['top_picks']) && is_array($race['top_picks'])) : ?>
                    <?php
                        $has_any_comment = false;
                        foreach ($race['top_picks'] as $cp) {
                            if (!empty($cp['comment_text']) || !empty($cp['comment_source'])) { $has_any_comment = true; break; }
                        }
                    ?>
                    <?php if ($has_any_comment) : ?>
                        <section class="bfv-detail-block">
                            <h4>コメント実データ</h4>
                            <div class="bfv-detail-wrap">
                                <table class="bfv-detail-table sticky-name-table bfv-comment-table">
                                    <tr><th>艇</th><th>状態</th><th>コメント</th><th>判定根拠</th></tr>
                                    <?php
                                        $comment_picks = $race['top_picks'];
                                        usort($comment_picks, function ($a, $b) { return (int) ($a['waku'] ?? 0) - (int) ($b['waku'] ?? 0); });
                                    ?>
                                    <?php foreach ($comment_picks as $cp) : ?>
                                        <?php
                                            $clabel = (string) ($cp['comment_label'] ?? '');
                                            if (strpos($clabel, '好') !== false || strpos($clabel, '▲') !== false) {
                                                $cmt_cls = 'cmt-good'; $cmt_mark = '▲';
                                            } elseif (strpos($clabel, '不') !== false || strpos($clabel, '▼') !== false) {
                                                $cmt_cls = 'cmt-bad'; $cmt_mark = '▼';
                                            } else {
                                                $cmt_cls = 'cmt-neutral'; $cmt_mark = '―';
                                            }
                                            $raw_score = $cp['comment_raw_score'] ?? '';
                                            $keywords = isset($cp['comment_matched_keywords']) && is_array($cp['comment_matched_keywords']) ? $cp['comment_matched_keywords'] : [];
                                        ?>
                                        <tr>
                                            <td><?php echo boat_forecast_viewer_render_waku_name($cp['waku'] ?? '', $cp['name'] ?? '', !empty($cp['is_female'])); ?></td>
                                            <td class="<?php echo esc_attr($cmt_cls); ?>"><?php echo esc_html($cmt_mark); ?></td>
                                            <td>
                                                <?php if (!empty($cp['comment_text'])) : ?>
                                                    <?php echo esc_html((string) $cp['comment_text']); ?>
                                                    <?php if (!empty($cp['comment_source'])) : ?>
                                                        <span class="bfv-dim">(<?php echo esc_html((string) $cp['comment_source']); ?>)</span>
                                                    <?php endif; ?>
                                                <?php else : ?>
                                                    <span class="bfv-dim">コメントなし</span>
                                                <?php endif; ?>
                                            </td>
                                            <td>
                                                <?php if (!empty($keywords)) : ?>
                                                    <?php echo esc_html(implode(' / ', $keywords)); ?>
                                                <?php else : ?>
                                                    <span class="bfv-dim">キーワード一致なし</span>
                                                <?php endif; ?>
                                                <?php if ($raw_score !== '' && $raw_score !== null) : ?>
                                                    <div class="bfv-cmt-keywords">raw <?php echo esc_html((string) $raw_score); ?></div>
                                                <?php endif; ?>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                </table>
                            </div>
                        </section>
                    <?php endif; ?>
                <?php endif; ?>

                <?php /* v5.18: 展示実データセクション */ ?>
                <?php if (!empty($race['exhibition_section']['rows']) && is_array($race['exhibition_section']['rows'])) : ?>
                    <section class="bfv-detail-block">
                        <h4>展示実データ</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table">
                                <tr><th>艇</th><th>展示T</th><th>チルト</th><th>進入</th><th>前走ST</th><th>前走着</th><th>評価</th></tr>
                                <?php foreach ($race['exhibition_section']['rows'] as $exrow) : ?>
                                    <?php
                                        $rating = (string) ($exrow['rating'] ?? '');
                                        $ex_cls = '';
                                        if (strpos($rating, '★') !== false) $ex_cls = 'ex-best';
                                        elseif (strpos($rating, '▲') !== false) $ex_cls = 'ex-good';
                                        elseif (strpos($rating, '▼') !== false) $ex_cls = 'ex-slow';
                                        $entry = (string) ($exrow['entry_course'] ?? '');
                                        $waku_str = (string) ($exrow['waku'] ?? '');
                                        $entry_warn = ($entry !== '' && $waku_str !== '' && $entry !== $waku_str) ? ' ⚠' : '';
                                    ?>
                                    <tr>
                                        <td><?php echo boat_forecast_viewer_render_waku_name($exrow['waku'] ?? '', $exrow['name'] ?? '', false); ?></td>
                                        <td><strong><?php echo esc_html((string) ($exrow['time'] ?? '')); ?></strong></td>
                                        <td><?php echo esc_html((string) ($exrow['tilt'] ?? '')); ?></td>
                                        <td><?php echo esc_html($entry . $entry_warn); ?></td>
                                        <td><?php echo esc_html((string) ($exrow['start_timing'] ?? '')); ?></td>
                                        <td><?php echo esc_html((string) ($exrow['prev_rank'] ?? '')); ?></td>
                                        <td class="<?php echo esc_attr($ex_cls); ?>"><?php echo esc_html($rating); ?></td>
                                    </tr>
                                <?php endforeach; ?>
                            </table>
                        </div>
                        <?php if (!empty($race['exhibition_section']['course_order']) && is_array($race['exhibition_section']['course_order'])) : ?>
                            <div class="bfv-exhibition-order">
                                スタート展示順:
                                <?php foreach ($race['exhibition_section']['course_order'] as $co) : ?>
                                    <?php
                                        $co_course = is_array($co) ? ($co['course'] ?? '') : $co;
                                        $co_st = is_array($co) ? ($co['st'] ?? '') : '';
                                        $co_foul = is_array($co) && !empty($co['foul']);
                                    ?>
                                    <?php echo esc_html($co_course); ?><?php if ($co_foul) echo '<span style="color:#c62828">[F]</span>'; ?><?php if ($co_st) echo '(' . esc_html($co_st) . ')'; ?>
                                <?php endforeach; ?>
                            </div>
                        <?php endif; ?>
                    </section>
                <?php endif; ?>

                <?php if (!empty($race['top_picks']) && is_array($race['top_picks'])) : ?>
                    <div class="bfv-picks">
                        <?php foreach ($race['top_picks'] as $pick) : ?>
                            <?php $mark = (string) ($pick['mark'] ?? ''); ?>
                            <section class="bfv-pick">
                                <span class="bfv-pick-mark<?php echo $mark === '' ? ' is-plain' : ''; ?>"><?php echo esc_html($mark); ?></span>
                                <div>
                                    <div class="bfv-pick-name">
                                        <?php echo boat_forecast_viewer_render_waku_name($pick['waku'] ?? '', $pick['name'] ?? '', !empty($pick['is_female'])); ?>
                                    </div>
                                    <div class="bfv-pick-meta">
                                        <span><?php echo esc_html((string) ($pick['waku'] ?? '')); ?>号艇</span>
                                        <?php if (!empty($pick['grade'])) : ?>
                                            <?php echo boat_forecast_viewer_render_grade($pick['grade']); ?>
                                        <?php endif; ?>
                                        <?php if (!empty($pick['comment_label'])) : ?>
                                            <span>コメント <?php echo esc_html((string) $pick['comment_label']); ?></span>
                                        <?php endif; ?>
                                        <?php if (!empty($pick['exhibition_time'])) : ?>
                                            <span>展示 <?php echo esc_html((string) $pick['exhibition_time']); ?></span>
                                        <?php endif; ?>
                                    </div>
                                    <?php if (!empty($pick['comment_text'])) : ?>
                                        <div class="bfv-pick-note"><?php echo esc_html((string) $pick['comment_text']); ?></div>
                                    <?php endif; ?>
                                </div>
                                <div class="bfv-score">score <?php echo esc_html(boat_forecast_viewer_format_decimal($pick['score'] ?? '', 2)); ?></div>
                            </section>
                        <?php endforeach; ?>
                    </div>
                <?php endif; ?>
                <?php if (!empty($race['detailed_predictions']) && is_array($race['detailed_predictions'])) : ?>
                    <?php $display_rows = boat_forecast_viewer_sort_rows_by_waku($race['detailed_predictions']); ?>
                    <section class="bfv-detail-block">
                        <h4>実データ</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table">
                                <tr>
                                    <th>順 / 艇</th>
                                    <th>全国勝率</th>
                                    <th>当地勝率</th>
                                    <th>モーター2連</th>
                                    <th>ボート2連</th>
                                    <th>平均ST</th>
                                    <th>今節成績</th>
                                    <th>展示</th>
                                    <th>コメント根拠</th>
                                </tr>
                                <?php foreach ($display_rows as $row) :
                                    $raw = isset($row['raw_metrics']) && is_array($row['raw_metrics']) ? $row['raw_metrics'] : [];
                                    $global = isset($raw['global_win']) && is_array($raw['global_win']) ? $raw['global_win'] : [];
                                    $local = isset($raw['local_win']) && is_array($raw['local_win']) ? $raw['local_win'] : [];
                                    $motor = isset($raw['motor_2rate']) && is_array($raw['motor_2rate']) ? $raw['motor_2rate'] : [];
                                    $boat = isset($raw['boat_2rate']) && is_array($raw['boat_2rate']) ? $raw['boat_2rate'] : [];
                                    $st = isset($raw['st']) && is_array($raw['st']) ? $raw['st'] : [];
                                    $series = isset($raw['series']) && is_array($raw['series']) ? $raw['series'] : [];
                                    $comment = isset($raw['comment']) && is_array($raw['comment']) ? $raw['comment'] : [];
                                    // v5.19 #3: コース-着順ペア表示（races 優先、無ければ ranks のみ）
                                    if (!empty($series['races']) && is_array($series['races'])) {
                                        $parts = [];
                                        foreach ($series['races'] as $sr) {
                                            if (!is_array($sr)) continue;
                                            $c = isset($sr['course']) ? (string)$sr['course'] : '?';
                                            $rk = isset($sr['rank']) ? (string)$sr['rank'] : '?';
                                            $parts[] = $c . '→' . $rk;
                                        }
                                        $ranks = $parts ? implode(' ', $parts) : '初日/実績なし';
                                    } elseif (!empty($series['ranks']) && is_array($series['ranks'])) {
                                        $ranks = implode(' ', $series['ranks']);
                                    } else {
                                        $ranks = '初日/実績なし';
                                    }
                                ?>
                                <tr>
                                    <td>
                                        <span class="bfv-rank-mark"><?php echo esc_html(boat_forecast_viewer_mark_for_rank($row['rank'] ?? 0)); ?></span>
                                        <?php echo boat_forecast_viewer_render_waku_name($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female'])); ?>
                                    </td>
                                    <td>今期 <?php echo esc_html((string) ($global['season_pct'] ?? '-')); ?> / 採用 <?php echo esc_html((string) ($global['adopted_pct'] ?? '-')); ?></td>
                                    <td>今期 <?php echo esc_html((string) ($local['season_pct'] ?? '-')); ?> / 採用 <?php echo esc_html((string) ($local['adopted_pct'] ?? '-')); ?></td>
                                    <td>今期 <?php echo esc_html((string) ($motor['season_pct'] ?? '-')); ?> / 採用 <?php echo esc_html((string) ($motor['adopted_pct'] ?? '-')); ?></td>
                                    <td><?php echo esc_html((string) ($boat['season_pct'] ?? '-')); ?></td>
                                    <td>出走表 <?php echo esc_html((string) ($st['racecard_avg'] ?? '-')); ?> / 実績 <?php echo esc_html((string) ($st['hist_avg'] ?? '-')); ?></td>
                                    <td><?php echo esc_html($ranks); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_render_exhibition_text(isset($raw['exhibition']) ? $raw['exhibition'] : [])); ?></td>
                                    <td>
                                        <div><?php echo esc_html((string) ($comment['source'] ?? '-')); ?></div>
                                        <div class="bfv-dim"><?php echo esc_html((string) ($comment['text'] ?? 'コメントなし')); ?></div>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </table>
                        </div>
                    </section>
                    <section class="bfv-detail-block">
                        <h4>枠別着順実績</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table">
                                <tr>
                                    <th>艇</th>
                                    <th>参照</th>
                                    <th>1着%</th>
                                    <th>2着%</th>
                                    <th>3着%</th>
                                    <th>3連内%</th>
                                    <th>全国1着%</th>
                                    <th>R数</th>
                                </tr>
                                <?php foreach ($display_rows as $row) :
                                    $picked = boat_forecast_viewer_pick_waku_stats($row);
                                    $stats = $picked['stats'];
                                    $global = isset($row['waku_stats']['global']) && is_array($row['waku_stats']['global']) ? $row['waku_stats']['global'] : [];
                                ?>
                                <tr>
                                    <td><?php echo boat_forecast_viewer_render_waku_name($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female'])); ?></td>
                                    <td><?php echo esc_html((string) $picked['label']); ?></td>
                                    <td><?php echo esc_html((string) ($stats['1st_pct'] ?? '---')); ?><?php echo boat_forecast_viewer_render_meter($stats['1st_pct'] ?? 0, 100, 'rank1'); ?></td>
                                    <td><?php echo esc_html((string) ($stats['2nd_pct'] ?? '---')); ?><?php echo boat_forecast_viewer_render_meter($stats['2nd_pct'] ?? 0, 100, 'rank2'); ?></td>
                                    <td><?php echo esc_html((string) ($stats['3rd_pct'] ?? '---')); ?><?php echo boat_forecast_viewer_render_meter($stats['3rd_pct'] ?? 0, 100, 'rank3'); ?></td>
                                    <td><?php echo esc_html((string) ($stats['top3_pct'] ?? '---')); ?><?php echo boat_forecast_viewer_render_meter($stats['top3_pct'] ?? 0, 100, 'top3'); ?></td>
                                    <td><?php echo esc_html((string) ($global['1st_pct'] ?? '---')); ?></td>
                                    <td><?php echo esc_html((string) ($stats['races'] ?? 0)); ?></td>
                                </tr>
                                <?php endforeach; ?>
                            </table>
                        </div>
                    </section>
                    <section class="bfv-detail-block">
                        <h4>システム計算ロジック</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table">
                                <tr>
                                    <th>艇</th>
                                    <th>級</th>
                                    <th>総合</th>
                                    <th>全勝寄与</th>
                                    <th>当地寄与</th>
                                    <th>モータ寄与</th>
                                    <th>コース寄与</th>
                                    <th>ST寄与</th>
                                    <th>展示寄与</th>
                                    <th>枠実績寄与</th>
                                    <th>コメ寄与</th>
                                    <th>エンジン補正</th>
                                </tr>
                                <?php foreach ($display_rows as $row) :
                                    $breakdown = isset($row['breakdown']) && is_array($row['breakdown']) ? $row['breakdown'] : [];
                                ?>
                                <tr>
                                    <td><?php echo boat_forecast_viewer_render_waku_name($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female'])); ?></td>
                                    <td><?php echo boat_forecast_viewer_render_grade($row['grade'] ?? ''); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($row['score'] ?? '', 2)); ?><?php echo boat_forecast_viewer_render_meter($row['score'] ?? 0, 1.0, 'score'); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['global_win_rate'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['local_win_rate'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['motor_2rate'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['course_advantage'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['st_score'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['exhibition_score'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['hist_waku_score'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['comment_score'] ?? '-', 2)); ?></td>
                                    <td><?php echo esc_html(boat_forecast_viewer_format_decimal($breakdown['engine_bonus'] ?? '—', 2)); ?></td>
                                </tr>
                                <?php endforeach; ?>
                            </table>
                        </div>
                    </section>
                <?php endif; ?>
                <div class="bfv-card-foot">
                    <a class="bfv-back-btn" href="#bfv-summary">↑ 早見表へ戻る</a>
                </div>
            </article>
        <?php endforeach; ?>
    </section>

    <?php if (!empty($payload['review_summary']) && is_array($payload['review_summary'])) : ?>
        <?php $review = $payload['review_summary']; ?>
        <section class="bfv-review" id="review">
            <div class="bfv-review-head">
                <div>
                    <h3>結果振り返り</h3>
                    <div class="bfv-review-meta">検証日 <?php echo esc_html((string) ($review['run_date'] ?? '')); ?> / 対象 <?php echo esc_html((string) ($review['date'] ?? '')); ?></div>
                </div>
                <?php if (!empty($review['detail_file'])) : ?>
                    <a class="bfv-review-link" href="<?php echo esc_url(home_url('/output/data/verify/' . $review['detail_file'])); ?>" target="_blank" rel="noopener noreferrer">検証詳細</a>
                <?php endif; ?>
            </div>
            <div class="bfv-review-grid">
                <div class="bfv-review-card is-primary">
                    <strong>1着的中</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_1st_pct'] ?? '-')); ?>%</div>
                </div>
                <div class="bfv-review-card is-primary">
                    <strong>レース的中</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_bet_any_pct'] ?? '-')); ?>%</div>
                    <div class="bfv-review-sub">買い目8点のいずれかが的中</div>
                </div>
                <div class="bfv-review-card">
                    <strong>本命</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_honmei_pct'] ?? '-')); ?>%</div>
                </div>
                <div class="bfv-review-card">
                    <strong>その他</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_others_pct'] ?? '-')); ?>%</div>
                    <?php
                        $tai = $review['hit_taikou_pct'] ?? 0;
                        $osh = $review['hit_oshi_pct'] ?? 0;
                        $ana = $review['hit_ana_pct'] ?? 0;
                        if ($tai || $osh || $ana) :
                    ?>
                    <div class="bfv-review-sub">対抗<?php echo esc_html($tai); ?>% / 抑え<?php echo esc_html($osh); ?>% / 穴<?php echo esc_html($ana); ?>%</div>
                    <?php endif; ?>
                </div>
            </div>
            <?php /* v5.18: 追加指標カード (R1+R2) */ ?>
            <?php
                $has_extra_cards = isset($review['hit_3fuku_pct']) || isset($review['hit_3tan_pct']) || isset($review['hit_2tan_pct']) || isset($review['hit_2fuku_pct']);
            ?>
            <?php if ($has_extra_cards) : ?>
                <div class="bfv-review-grid-extra">
                    <?php if (isset($review['hit_3fuku_pct'])) : ?>
                        <div class="bfv-review-card"><strong>3連複</strong><div class="bfv-review-value"><?php echo esc_html((string) $review['hit_3fuku_pct']); ?>%</div></div>
                    <?php endif; ?>
                    <?php if (isset($review['hit_3tan_pct'])) : ?>
                        <div class="bfv-review-card"><strong>3連単</strong><div class="bfv-review-value"><?php echo esc_html((string) $review['hit_3tan_pct']); ?>%</div></div>
                    <?php endif; ?>
                    <?php if (isset($review['hit_2tan_pct'])) : ?>
                        <div class="bfv-review-card"><strong>2連単</strong><div class="bfv-review-value"><?php echo esc_html((string) $review['hit_2tan_pct']); ?>%</div></div>
                    <?php endif; ?>
                    <?php if (isset($review['hit_2fuku_pct'])) : ?>
                        <div class="bfv-review-card"><strong>2連複</strong><div class="bfv-review-value"><?php echo esc_html((string) $review['hit_2fuku_pct']); ?>%</div></div>
                    <?php endif; ?>
                </div>
            <?php endif; ?>
            <?php /* v5.18: 平均配当・平均人気・高配当レース (R3+R4) */ ?>
            <?php if (!empty($review['avg_pay']) || !empty($review['avg_pop'])) : ?>
                <div class="bfv-review-info">
                    <?php if (!empty($review['avg_pay'])) : ?>
                        <span>平均配当: <?php echo esc_html(number_format((int) $review['avg_pay'])); ?>円</span>
                    <?php endif; ?>
                    <?php if (!empty($review['avg_pop'])) : ?>
                        <span>平均人気: <?php echo esc_html((string) $review['avg_pop']); ?>番人気</span>
                    <?php endif; ?>
                </div>
            <?php endif; ?>
            <?php if (!empty($review['big_upsets']) && is_array($review['big_upsets'])) : ?>
                <ul class="bfv-review-upsets">
                    <?php foreach ($review['big_upsets'] as $upset) : ?>
                        <li>高配当: <?php echo esc_html((string) ($upset['race_no'] ?? '')); ?>R — <?php echo esc_html(number_format((int) ($upset['payout'] ?? 0))); ?>円 (<?php echo esc_html((string) ($upset['popularity'] ?? '')); ?>番人気) 結果 <?php echo esc_html((string) ($upset['won3'] ?? '')); ?></li>
                    <?php endforeach; ?>
                </ul>
            <?php endif; ?>
            <?php if (!empty($review['summary_lines']) || !empty($review['trend_lines']) || !empty($review['race_lines'])) : ?>
                <div class="bfv-review-blocks">
                    <?php if (!empty($review['summary_lines']) && is_array($review['summary_lines'])) : ?>
                        <div class="bfv-review-block">
                            <h4>集計メモ</h4>
                            <ul class="bfv-review-list">
                                <?php foreach ($review['summary_lines'] as $line) : ?>
                                    <li><?php echo esc_html((string) $line); ?></li>
                                <?php endforeach; ?>
                            </ul>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($review['trend_lines']) && is_array($review['trend_lines'])) : ?>
                        <div class="bfv-review-block">
                            <h4>傾向コメント</h4>
                            <ul class="bfv-review-list">
                                <?php foreach ($review['trend_lines'] as $line) : ?>
                                    <li><?php echo esc_html((string) $line); ?></li>
                                <?php endforeach; ?>
                            </ul>
                        </div>
                    <?php endif; ?>
                    <?php if ((empty($review['race_table']['rows'])) && !empty($review['race_lines']) && is_array($review['race_lines'])) : ?>
                        <div class="bfv-review-block">
                            <h4>レース別結果</h4>
                            <div class="bfv-review-races">
                                <?php foreach ($review['race_lines'] as $line) : ?>
                                    <div class="bfv-review-race"><?php echo esc_html((string) $line); ?></div>
                                <?php endforeach; ?>
                            </div>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($review['race_table']['headers']) && !empty($review['race_table']['rows'])) : ?>
                        <div class="bfv-review-block">
                            <h4>レース別結果一覧</h4>
                            <div class="bfv-review-table-wrap">
                                <table class="bfv-review-table">
                                    <tr>
                                        <?php foreach ($review['race_table']['headers'] as $header) : ?>
                                            <th><?php echo esc_html((string) $header); ?></th>
                                        <?php endforeach; ?>
                                    </tr>
                                    <?php foreach ($review['race_table']['rows'] as $row) : ?>
                                        <tr>
                                            <?php $last_idx = count($row) - 1; ?>
                                            <?php foreach ($row as $idx => $cell) : ?>
                                                <?php
                                                    $td_cls = '';
                                                    if ($idx === 1) $td_cls = 'is-sticky-second';
                                                    if ($idx === $last_idx) {
                                                        $cell_str = (string) $cell;
                                                        if (strpos($cell_str, '買い目的中') !== false) $td_cls = 'verdict-hit';
                                                        elseif (strpos($cell_str, '3連単一致') !== false) $td_cls = 'verdict-order';
                                                        elseif (strpos($cell_str, '3連複') !== false) $td_cls = 'verdict-box';
                                                        elseif (strpos($cell_str, '不的中') !== false) $td_cls = 'verdict-miss';
                                                    }
                                                ?>
                                                <td<?php echo $td_cls ? ' class="' . esc_attr($td_cls) . '"' : ''; ?>><?php echo esc_html((string) $cell); ?></td>
                                            <?php endforeach; ?>
                                        </tr>
                                    <?php endforeach; ?>
                                </table>
                            </div>
                        </div>
                    <?php endif; ?>
                    <?php if (!empty($review['bet_history_table']['headers']) && !empty($review['bet_history_table']['rows'])) : ?>
                        <div class="bfv-review-block">
                            <h4>買い目別命中履歴</h4>
                            <div class="bfv-review-table-wrap">
                                <table class="bfv-review-table">
                                    <tr>
                                        <?php foreach ($review['bet_history_table']['headers'] as $header) : ?>
                                            <th><?php echo esc_html((string) $header); ?></th>
                                        <?php endforeach; ?>
                                    </tr>
                                    <?php foreach ($review['bet_history_table']['rows'] as $row) : ?>
                                        <tr>
                                            <?php foreach ($row as $idx => $cell) : ?>
                                                <td<?php echo $idx === 1 ? ' class="is-sticky-second"' : ''; ?>><?php echo esc_html((string) $cell); ?></td>
                                            <?php endforeach; ?>
                                        </tr>
                                    <?php endforeach; ?>
                                </table>
                            </div>
                        </div>
                    <?php endif; ?>
                </div>
            <?php endif; ?>
        </section>
    <?php endif; ?>

    <p class="bfv-foot"><a href="<?php echo esc_url(get_post_type_archive_link('forecast_day') ?: home_url('/race/')); ?>">開催一覧へ戻る</a></p>
</div>
</body>
</html>
<?php
}

function boat_forecast_viewer_render_archive($query) {
    $posts = $query->posts;
    $venue_slug = get_query_var('bfv_venue');
    $venue_map = boat_forecast_viewer_venue_map();
    $venue_name = isset($venue_map[$venue_slug]) ? $venue_map[$venue_slug] : strtoupper((string) $venue_slug);
    $venues = boat_forecast_viewer_collect_archive_items();
    ?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Race Forecast Archive</title>
<?php echo boat_forecast_viewer_font_links(); ?>
    <style>
<?php echo boat_forecast_viewer_common_root_css(); ?>
        /* ===== Phase 5: archive (grid view, row-list cards) ===== */
        body {
            margin: 0;
            background: var(--bfv-bg);
            color: var(--bfv-ink);
            font-family: var(--bfv-font-sans);
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        a { color: inherit; }

        .bfva-shell {
            width: min(1120px, calc(100% - 24px));
            margin: 0 auto;
            padding: 20px 0 72px;
        }

        /* ===== HERO (compact, single line) ===== */
        .bfva-hero {
            background: var(--bfv-surface);
            color: var(--bfv-ink);
            border: 1px solid var(--bfv-line);
            border-radius: var(--bfv-radius-md);
            padding: 14px 18px;
            box-shadow: var(--bfv-shadow-xs);
            display: flex;
            align-items: baseline;
            gap: 14px;
            margin-bottom: 14px;
        }
        .bfva-hero h1 {
            margin: 0;
            font-size: clamp(18px, 2.8vw, 22px);
            letter-spacing: 0.02em;
            font-feature-settings: "palt";
        }
        .bfva-hero p {
            display: block;
            margin: 0;
            color: var(--bfv-muted);
            font-size: 12px;
            font-family: var(--bfv-font-mono);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .bfva-hero-count {
            margin-left: auto;
            font-family: var(--bfv-font-mono);
            font-size: 12px;
            color: var(--bfv-ink-sub);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        /* ===== GRID ===== */
        .bfva-grid {
            display: grid;
            gap: 10px;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        }

        /* ===== CARD ===== */
        .bfva-card {
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-line);
            border-radius: var(--bfv-radius-md);
            padding: 0;
            overflow: hidden;
            box-shadow: var(--bfv-shadow-xs);
            transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
            display: flex;
            flex-direction: column;
        }
        .bfva-card:hover {
            transform: translateY(-1px);
            box-shadow: var(--bfv-shadow-md);
            border-color: var(--bfv-line-strong);
        }

        /* card header */
        .bfva-card-head {
            padding: 12px 14px 10px;
            border-bottom: 1px solid var(--bfv-line);
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 0;
        }
        .bfva-card-head-left {
            display: flex;
            align-items: baseline;
            gap: 8px;
            min-width: 0;
        }
        .bfva-card h2 {
            margin: 0;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: -0.005em;
        }
        .bfva-card-slug {
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            color: var(--bfv-muted);
        }
        .bfva-card-link {
            color: var(--bfv-ink);
            text-decoration: none;
        }
        .bfva-card-link:hover { color: var(--bfv-accent); }
        .bfva-card-date {
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            color: var(--bfv-ink-sub);
            white-space: nowrap;
        }

        /* card meta row */
        .bfva-card-meta {
            padding: 8px 14px;
            border-bottom: 1px solid var(--bfv-line);
            display: flex;
            gap: 14px;
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            color: var(--bfv-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .bfva-card-meta strong {
            color: var(--bfv-ink);
            font-weight: 600;
            font-size: 13px;
            margin-right: 4px;
            text-transform: none;
        }

        /* history row list (replaces the chip row) */
        .bfva-card-list {
            display: flex;
            flex-direction: column;
        }
        .bfva-card-row {
            display: grid;
            grid-template-columns: 10px 1fr auto;
            gap: 10px;
            align-items: center;
            padding: 8px 14px;
            color: var(--bfv-ink-sub);
            text-decoration: none;
            font-family: var(--bfv-font-mono);
            font-size: 11px;
            border-bottom: 1px solid rgba(26,25,21,0.04);
        }
        .bfva-card-row:last-child { border-bottom: 0; }
        .bfva-card-row:hover {
            background: var(--bfv-surface-sub);
            color: var(--bfv-ink);
        }
        .bfva-card-row-dot {
            width: 6px;
            height: 6px;
            border-radius: 1px;
            background: var(--bfv-line-strong);
        }
        .bfva-card-row.has-review .bfva-card-row-dot {
            background: var(--bfv-accent);
        }
        .bfva-card-row-date {
            color: inherit;
        }
        .bfva-card-row-tag {
            font-size: 9px;
            color: var(--bfv-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .bfva-card-row.has-review .bfva-card-row-tag {
            color: var(--bfv-accent);
        }

        /* card footer (cta) */
        .bfva-card-foot {
            margin-top: auto;
            padding: 8px 14px;
            background: var(--bfv-surface-sub);
            border-top: 1px solid var(--bfv-line);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .bfva-card-foot-meta {
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            color: var(--bfv-muted);
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .bfva-card-cta {
            font-family: var(--bfv-font-mono);
            font-size: 11px;
            font-weight: 600;
            color: var(--bfv-accent);
            text-decoration: none;
            letter-spacing: 0.04em;
        }
        .bfva-card-cta::after { content: " →"; }

        /* ===== venue-specific list view (Phase 5範囲外、維持) ===== */
        .bfva-meta { color: var(--bfv-ink-sub); font-size: 14px; display: grid; gap: 6px; }
        .bfva-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
        .bfva-badge { background: var(--bfv-surface-sub); padding: 6px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; border: 1px solid var(--bfv-line); }
        .bfva-badge.is-review { background: var(--bfv-ink); color: #fff; border-color: var(--bfv-ink); }
        .bfva-crumbs {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 0 0 14px;
            color: var(--bfv-muted);
            font-size: 14px;
        }
        .bfva-crumbs a { color: inherit; text-decoration: none; }
        .bfva-crumbs a:hover { text-decoration: underline; }
        .bfva-list {
            display: grid;
            gap: 12px;
            margin-top: 18px;
        }
        .bfva-row {
            display: grid;
            gap: 12px;
            grid-template-columns: minmax(0, 1.2fr) minmax(220px, .8fr);
            padding: 16px 18px;
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-line);
            border-radius: var(--bfv-radius-md);
            box-shadow: var(--bfv-shadow-xs);
        }
        .bfva-row h2 { margin: 0 0 8px; font-size: 22px; }
        .bfva-side { display: grid; gap: 8px; align-content: start; }
        .bfva-side a { color: var(--bfv-ink); text-decoration: none; font-weight: 700; }
        .bfva-side a:hover { color: var(--bfv-accent); }

        @media (max-width: 720px) {
            .bfva-row { grid-template-columns: 1fr; }
        }
        @media (max-width: 640px) {
            .bfva-shell { width: calc(100% - 16px); padding-top: 14px; }
            .bfva-hero { padding: 12px 14px; }
            .bfva-grid { grid-template-columns: 1fr; gap: 8px; }
        }

        /* ===== グローバルナビ (archive) ===== */
        .bfv-gnav {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
            margin-bottom: 14px;
            padding: 8px 12px;
            background: rgba(255,255,255,.85);
            border: 1px solid var(--bfv-line);
            border-radius: 999px;
            backdrop-filter: blur(8px);
        }
        .bfv-gnav-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            color: var(--bfv-ink);
            text-decoration: none;
            transition: background .15s, color .15s;
        }
        .bfv-gnav-link:hover { background: rgba(26,25,21,.06); text-decoration: none; }
        .bfv-gnav-active { background: var(--bfv-ink) !important; color: #fff !important; }
    </style>
</head>
<body>
<div class="bfva-shell">
    <?php boat_forecast_viewer_render_nav('archive'); ?>
    <?php if ($venue_slug) : ?>
        <header class="bfva-hero">
            <h1><?php echo esc_html($venue_name); ?></h1>
            <p>Forecast Archive</p>
        </header>
    <?php else : ?>
        <header class="bfva-hero">
            <h1>会場一覧</h1>
            <p>Forecast Archive</p>
            <span class="bfva-hero-count"><?php echo count($venues); ?> venues</span>
        </header>
    <?php endif; ?>
    <?php if ($venue_slug) : ?>
        <nav class="bfva-crumbs">
            <a href="<?php echo esc_url(get_post_type_archive_link('forecast_day') ?: home_url('/race/')); ?>">会場一覧</a>
            <span>/</span>
            <span><?php echo esc_html($venue_name); ?></span>
        </nav>
        <section class="bfva-list">
            <?php foreach ($posts as $post) : ?>
                <?php $payload = boat_forecast_viewer_load_payload($post->ID); ?>
                <div class="bfva-row">
                    <div>
                        <h2><a href="<?php echo esc_url(get_permalink($post)); ?>"><?php echo esc_html(get_the_title($post)); ?></a></h2>
                        <div class="bfva-meta">
                            <span>日付: <?php echo esc_html((string) ($payload['date'] ?? get_post_meta($post->ID, 'race_date', true))); ?></span>
                            <span>最終更新: <?php echo esc_html((string) ($payload['updated_at'] ?? get_post_meta($post->ID, 'updated_at', true))); ?></span>
                        </div>
                        <div class="bfva-badges">
                            <span class="bfva-badge"><?php echo !empty($payload['has_exhibition']) ? '展示反映' : '展示未反映'; ?></span>
                            <span class="bfva-badge"><?php echo !empty($payload['has_odds']) ? 'オッズ反映' : 'オッズ未反映'; ?></span>
                            <span class="bfva-badge"><?php echo esc_html((string) get_post_meta($post->ID, 'publish_stage', true)); ?></span>
                            <?php if (!empty($payload['review_summary'])) : ?>
                                <span class="bfva-badge is-review">振り返りあり</span>
                            <?php endif; ?>
                        </div>
                    </div>
                    <div class="bfva-side">
                        <a href="<?php echo esc_url(get_permalink($post)); ?>">開催詳細を見る</a>
                        <?php if (!empty($payload['review_summary'])) : ?>
                            <a href="<?php echo esc_url(get_permalink($post) . '#review'); ?>">振り返りを見る</a>
                        <?php endif; ?>
                    </div>
                </div>
            <?php endforeach; ?>
        </section>
    <?php else : ?>
        <div class="bfva-grid">
        <?php foreach ($venues as $venue):
            $latest_link = !empty($venue['latest_link']) ? $venue['latest_link'] : home_url('/race/' . $venue['slug'] . '/');
            $items = isset($venue['items']) && is_array($venue['items']) ? $venue['items'] : [];
        ?>
            <article class="bfva-card">
                <div class="bfva-card-head">
                    <div class="bfva-card-head-left">
                        <h2><a class="bfva-card-link" href="<?php echo esc_url($latest_link); ?>"><?php echo esc_html($venue['name']); ?></a></h2>
                        <span class="bfva-card-slug">/<?php echo esc_html($venue['slug']); ?></span>
                    </div>
                    <span class="bfva-card-date"><?php echo esc_html($venue['latest_date']); ?></span>
                </div>

                <div class="bfva-card-meta">
                    <span><strong><?php echo (int) $venue['count']; ?></strong>予想</span>
                    <span><strong><?php echo (int) $venue['review_count']; ?></strong>振り返り</span>
                </div>

                <div class="bfva-card-list">
                    <?php foreach ($items as $item): ?>
                        <a class="bfva-card-row<?php echo !empty($item['has_review']) ? ' has-review' : ''; ?>"
                           href="<?php echo esc_url(!empty($item['has_review']) ? ($item['link'] . '#review') : $item['link']); ?>"
                           title="<?php echo esc_attr((string) ($item['title'] ?? '')); ?>">
                            <span class="bfva-card-row-dot" aria-hidden="true"></span>
                            <span class="bfva-card-row-date"><?php echo esc_html((string) $item['date']); ?></span>
                            <span class="bfva-card-row-tag"><?php echo !empty($item['has_review']) ? '振返済' : '予想のみ'; ?></span>
                        </a>
                    <?php endforeach; ?>
                </div>

                <div class="bfva-card-foot">
                    <span class="bfva-card-foot-meta"><?php echo (int) $venue['count']; ?>R記録 · <?php echo (int) $venue['review_count']; ?>R振返済</span>
                    <a class="bfva-card-cta" href="<?php echo esc_url($latest_link); ?>">詳細</a>
                </div>
            </article>
        <?php endforeach; ?>
        </div>
    <?php endif; ?>
</div>
</body>
</html>
<?php
}

function boat_forecast_viewer_render_review() {
    $posts = get_posts([
        'post_type'    => 'forecast_day',
        'post_status'  => 'publish',
        'numberposts'  => -1,
        'orderby'      => 'date',
        'order'        => 'DESC',
    ]);

    $all_items        = [];
    $total_races      = 0;
    $weighted_any_sum = 0.0;
    foreach ($posts as $post) {
        $payload = boat_forecast_viewer_load_payload($post->ID);
        if (empty($payload['review_summary']) || !is_array($payload['review_summary'])) {
            continue;
        }
        $review     = $payload['review_summary'];
        $venue_slug = (string) ($payload['venue_slug'] ?? get_post_meta($post->ID, 'venue_slug', true));
        $venue_name = (string) ($payload['venue_name'] ?? get_post_meta($post->ID, 'venue_name', true));
        $race_date  = (string) ($payload['date']       ?? get_post_meta($post->ID, 'race_date', true));
        $races_cnt  = (int)    ($review['total_races']     ?? 0);
        $any_pct    = (float)  ($review['hit_bet_any_pct'] ?? 0);
        $total_races      += $races_cnt;
        $weighted_any_sum += $races_cnt * $any_pct;
        $all_items[] = [
            'post'       => $post,
            'venue_slug' => $venue_slug,
            'venue_name' => $venue_name ?: $venue_slug,
            'race_date'  => $race_date,
            'review'     => $review,
            'link'       => get_permalink($post) . '#review',
        ];
    }
    $overall_rate   = ($total_races > 0) ? round($weighted_any_sum / $total_races, 1) : 0;
    $total_hits_est = ($total_races > 0) ? (int) round($total_races * $overall_rate / 100) : 0;

    // ── 月別グルーピング ──────────────────────────────
    $current_month = date('Y-m');  // "2026-04"
    $month_groups  = [];           // ['2026-04' => [...items...], ...]
    foreach ($all_items as $item) {
        $d = $item['race_date'];
        if (preg_match('/^(\d{4})-(\d{2})/', $d, $m)) {
            $mk = $m[1] . '-' . $m[2];
        } elseif (preg_match('/^(\d{4})(\d{2})/', $d, $m)) {
            $mk = $m[1] . '-' . $m[2];
        } else {
            $mk = 'unknown';
        }
        $month_groups[$mk][] = $item;
    }
    krsort($month_groups);  // 新しい月を先頭に
    ?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>振り返り一覧 — ボートレース予想</title>
<?php echo boat_forecast_viewer_font_links(); ?>
    <style>
<?php echo boat_forecast_viewer_common_root_css(); ?>
        *, *::before, *::after { box-sizing: border-box; }
        body {
            margin: 0;
            background: var(--bfv-bg);
            color: var(--bfv-ink);
            font-family: var(--bfv-font-sans);
            line-height: 1.55;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        a { color: inherit; }
        .bfrv-shell {
            width: min(1120px, calc(100% - 24px));
            margin: 0 auto;
            padding: 20px 0 72px;
        }

        /* ==== HERO ==== */
        .bfrv-hero {
            background: var(--bfv-hero-ink);
            color: #fff;
            border-radius: var(--bfv-radius-md);
            padding: 24px 26px 22px;
            box-shadow: var(--bfv-shadow-sm);
            margin-bottom: 18px;
        }
        .bfrv-kicker {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(255,255,255,.10);
            color: rgba(255,255,255,.82);
            margin-bottom: 12px;
        }
        .bfrv-hero h1 {
            margin: 0 0 6px;
            font-size: clamp(24px, 4.2vw, 34px);
            letter-spacing: 0.02em;
            font-feature-settings: "palt";
        }
        .bfrv-hero p {
            margin: 0;
            color: rgba(255,255,255,.70);
            font-size: 13px;
        }

        .bfrv-stats {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 18px;
        }
        .bfrv-stat {
            background: rgba(255,255,255,.06);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: var(--bfv-radius-md);
            padding: 12px 14px;
            text-align: left;
            min-width: 0;
        }
        .bfrv-stat strong {
            display: block;
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(255,255,255,.55);
            margin-bottom: 6px;
        }
        .bfrv-stat span {
            font-family: var(--bfv-font-mono);
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.02em;
            font-variant-numeric: tabular-nums;
            color: #fff;
        }
        @media (max-width: 640px) {
            .bfrv-stats { grid-template-columns: repeat(2, 1fr); }
            .bfrv-stat span { font-size: 22px; }
        }

        /* ==== NAV (既存の .bfv-gnav がここに出力される) ==== */
        .bfv-gnav {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            align-items: center;
            margin-bottom: 14px;
            padding: 6px 10px;
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-line);
            border-radius: 999px;
        }
        .bfv-gnav-link {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            color: var(--bfv-ink);
            text-decoration: none;
            transition: background .15s, color .15s;
        }
        .bfv-gnav-link:hover { background: var(--bfv-surface-sub); }
        .bfv-gnav-active { background: var(--bfv-ink) !important; color: #fff !important; }

        /* ==== MONTH GROUPS ==== */
        .bfrv-month-section { margin-top: 22px; }
        .bfrv-month-header,
        details.bfrv-month-details > summary {
            display: flex;
            align-items: baseline;
            gap: 14px;
            font-size: 14px;
            font-weight: 700;
            color: var(--bfv-ink);
            padding: 10px 2px;
            background: transparent;
            border-radius: 0;
            border-bottom: 1px solid var(--bfv-line);
            margin-bottom: 10px;
            user-select: none;
        }
        .bfrv-month-header > span:first-child,
        details.bfrv-month-details > summary > span:first-child {
            font-size: 18px;
            letter-spacing: 0.02em;
        }
        .bfrv-month-header .bfrv-month-badge {
            font-family: var(--bfv-font-mono);
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 999px;
            background: var(--bfv-accent);
            color: #fff;
        }
        .bfrv-month-header .bfrv-month-stat,
        details.bfrv-month-details .bfrv-month-stat {
            margin-left: auto;
            font-family: var(--bfv-font-mono);
            font-size: 11px;
            color: var(--bfv-muted);
            letter-spacing: 0.04em;
        }

        details.bfrv-month-details { margin-top: 28px; }
        details.bfrv-month-details > summary {
            cursor: pointer;
            list-style: none;
        }
        details.bfrv-month-details > summary::-webkit-details-marker { display: none; }
        details.bfrv-month-details > summary::before {
            content: "▶";
            font-size: 9px;
            color: var(--bfv-muted);
            transition: transform .2s;
            margin-right: 4px;
        }
        details.bfrv-month-details[open] > summary::before { transform: rotate(90deg); }
        details.bfrv-month-details .bfrv-list { margin-top: 10px; }

        /* ==== ROW LIST ==== */
        .bfrv-list { display: grid; gap: 8px; }
        .bfrv-row {
            background: var(--bfv-surface);
            border: 1px solid var(--bfv-line);
            border-radius: var(--bfv-radius-md);
            padding: 14px 16px;
            box-shadow: var(--bfv-shadow-xs);
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items: center;
            transition: border-color .15s, box-shadow .15s;
        }
        .bfrv-row:hover {
            border-color: var(--bfv-line-strong);
            box-shadow: var(--bfv-shadow-sm);
        }
        .bfrv-row-title {
            margin: 0 0 6px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.01em;
            display: flex;
            align-items: baseline;
            gap: 10px;
            flex-wrap: wrap;
        }
        .bfrv-row-title > span {
            font-family: var(--bfv-font-mono);
            font-size: 12px;
            font-weight: 500;
            color: var(--bfv-muted);
        }
        .bfrv-row-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            font-size: 12px;
            color: var(--bfv-ink-sub);
        }
        .bfrv-pill {
            display: inline-flex;
            align-items: center;
            padding: 3px 9px;
            border-radius: 999px;
            font-family: var(--bfv-font-mono);
            font-size: 11px;
            font-weight: 600;
            background: var(--bfv-surface-sub);
            color: var(--bfv-ink-sub);
            letter-spacing: 0.02em;
            font-variant-numeric: tabular-nums;
        }
        .bfrv-pill.is-good { background: var(--bfv-good-soft); color: var(--bfv-good); }
        .bfrv-pill.is-mid  { background: #fcf5e3; color: #8a6420; }
        .bfrv-pill.is-low  { background: var(--bfv-warn-soft); color: var(--bfv-warn); }

        .bfrv-summary-lines {
            margin: 10px 0 0;
            padding-left: 16px;
            font-size: 12px;
            color: var(--bfv-muted);
            list-style: disc;
        }
        .bfrv-summary-lines li { margin-top: 2px; }

        .bfrv-link-btn {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 7px 14px;
            border-radius: 999px;
            background: transparent;
            border: 1px solid var(--bfv-line-strong);
            color: var(--bfv-ink);
            text-decoration: none;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.02em;
            white-space: nowrap;
            transition: background .15s, color .15s, border-color .15s;
        }
        .bfrv-link-btn:hover {
            background: var(--bfv-accent);
            color: #fff;
            border-color: var(--bfv-accent);
        }

        .bfrv-empty {
            text-align: center;
            padding: 56px 20px;
            color: var(--bfv-muted);
            font-size: 14px;
            background: var(--bfv-surface);
            border: 1px dashed var(--bfv-line-strong);
            border-radius: var(--bfv-radius-md);
        }

        @media (max-width: 640px) {
            .bfrv-row { grid-template-columns: 1fr; }
            .bfrv-link-btn { justify-self: start; }
        }
    </style>
</head>
<body>
<div class="bfrv-shell">
    <?php boat_forecast_viewer_render_nav('review'); ?>
    <section class="bfrv-hero">
        <span class="bfrv-kicker">Review · 振り返り</span>
        <h1>振り返り一覧</h1>
        <p>振り返りデータがある開催をまとめています。</p>
        <div class="bfrv-stats">
            <div class="bfrv-stat">
                <strong>対象開催数</strong>
                <span><?php echo esc_html((string) count($all_items)); ?></span>
            </div>
            <div class="bfrv-stat">
                <strong>累計レース数</strong>
                <span><?php echo esc_html((string) $total_races); ?></span>
            </div>
            <div class="bfrv-stat">
                <strong>推定的中数</strong>
                <span><?php echo esc_html((string) $total_hits_est); ?></span>
            </div>
            <div class="bfrv-stat is-primary">
                <strong>通算買い目的中率</strong>
                <span><?php echo esc_html((string) $overall_rate); ?>%</span>
            </div>
        </div>
    </section>

    <?php if (empty($all_items)) : ?>
        <div class="bfrv-empty">振り返りデータがある開催はまだありません。</div>
    <?php else : ?>

        <?php
        // ── 月別サマリを計算するヘルパークロージャ ──
        $month_label = function (string $mk): string {
            if (preg_match('/^(\d{4})-(\d{2})$/', $mk, $m)) {
                return $m[1] . '年' . ltrim($m[2], '0') . '月';
            }
            return $mk;
        };
        $month_stat = function (array $group): string {
            $r = 0; $w = 0.0;
            foreach ($group as $it) {
                $rc = (int)   ($it['review']['total_races']     ?? 0);
                $ap = (float) ($it['review']['hit_bet_any_pct'] ?? 0);
                $r += $rc; $w += $rc * $ap;
            }
            $rate = $r > 0 ? round($w / $r, 1) : 0;
            return count($group) . '件 / 買い目的中 ' . number_format($rate, 1) . '%';
        };

        foreach ($month_groups as $mk => $group) :
            $is_current = ($mk === $current_month);
        ?>

        <?php if ($is_current) : ?>
            <div class="bfrv-month-section">
                <div class="bfrv-month-header">
                    <span><?php echo esc_html($month_label($mk)); ?></span>
                    <span class="bfrv-month-badge">当月</span>
                    <span class="bfrv-month-stat"><?php echo esc_html($month_stat($group)); ?></span>
                </div>
                <div class="bfrv-list">
        <?php else : ?>
            <details class="bfrv-month-details">
                <summary>
                    <span><?php echo esc_html($month_label($mk)); ?></span>
                    <span class="bfrv-month-stat"><?php echo esc_html($month_stat($group)); ?></span>
                </summary>
                <div class="bfrv-list">
        <?php endif; ?>

                    <?php foreach ($group as $item) :
                        $review    = $item['review'];
                        $races_n   = (int)   ($review['total_races']     ?? 0);
                        $any_pct   = (float) ($review['hit_bet_any_pct'] ?? 0);
                        $first_pct = (float) ($review['hit_1st_pct']     ?? 0);
                        $fuku_pct  = (float) ($review['hit_3fuku_pct']   ?? 0);
                        $tan_pct   = (float) ($review['hit_3tan_pct']    ?? 0);
                        $est_hits  = $races_n > 0 ? (int) round($races_n * $any_pct / 100) : 0;
                        if    ($any_pct >= 55) { $pill_class = 'is-good'; }
                        elseif ($any_pct >= 35) { $pill_class = 'is-mid'; }
                        else                   { $pill_class = 'is-low'; }
                    ?>
                        <div class="bfrv-row">
                            <div>
                                <h2 class="bfrv-row-title">
                                    <?php echo esc_html($item['venue_name']); ?>
                                    <span style="font-weight:400;font-size:15px;color:#52606d;"><?php echo esc_html($item['race_date']); ?></span>
                                </h2>
                                <div class="bfrv-row-meta">
                                    <span class="bfrv-pill <?php echo esc_attr($pill_class); ?>">買い目的中 <?php echo esc_html(number_format($any_pct, 1)); ?>%</span>
                                    <span class="bfrv-pill">推定<?php echo esc_html((string) $est_hits); ?>/<?php echo esc_html((string) $races_n); ?> R</span>
                                    <?php if ($first_pct > 0) : ?>
                                        <span class="bfrv-pill">1着 <?php echo esc_html(number_format($first_pct, 1)); ?>%</span>
                                    <?php endif; ?>
                                    <?php if ($fuku_pct > 0) : ?>
                                        <span class="bfrv-pill">3連複 <?php echo esc_html(number_format($fuku_pct, 1)); ?>%</span>
                                    <?php endif; ?>
                                    <?php if ($tan_pct > 0) : ?>
                                        <span class="bfrv-pill">3連単 <?php echo esc_html(number_format($tan_pct, 1)); ?>%</span>
                                    <?php endif; ?>
                                    <?php if (!empty($review['avg_rank'])) : ?>
                                        <span class="bfrv-pill">平均着順 <?php echo esc_html((string) $review['avg_rank']); ?></span>
                                    <?php endif; ?>
                                </div>
                                <?php if (!empty($review['summary_lines']) && is_array($review['summary_lines'])) : ?>
                                    <ul class="bfrv-summary-lines">
                                        <?php foreach (array_slice($review['summary_lines'], 0, 3) as $line) : ?>
                                            <li><?php echo esc_html((string) $line); ?></li>
                                        <?php endforeach; ?>
                                    </ul>
                                <?php endif; ?>
                            </div>
                            <div>
                                <a class="bfrv-link-btn" href="<?php echo esc_url($item['link']); ?>">詳細を見る →</a>
                            </div>
                        </div>
                    <?php endforeach; ?>

                </div>

        <?php if ($is_current) : ?>
            </div><!-- /.bfrv-month-section -->
        <?php else : ?>
            </details>
        <?php endif; ?>

        <?php endforeach; ?>

    <?php endif; ?>
</div>
</body>
</html>
<?php
}

function boat_forecast_viewer_template_include($template) {
    if (is_singular('forecast_day')) {
        return BOAT_FORECAST_VIEWER_DIR . '/single-forecast-day.php';
    }
    if (is_post_type_archive('forecast_day')) {
        return BOAT_FORECAST_VIEWER_DIR . '/archive-forecast-day.php';
    }
    if (get_query_var('bfv_review')) {
        return BOAT_FORECAST_VIEWER_DIR . '/review-forecast.php';
    }
    return $template;
}
add_filter('template_include', 'boat_forecast_viewer_template_include');

function boat_forecast_viewer_activate() {
    boat_forecast_viewer_add_rewrite_rules();
    flush_rewrite_rules();
}
register_activation_hook(__FILE__, 'boat_forecast_viewer_activate');
