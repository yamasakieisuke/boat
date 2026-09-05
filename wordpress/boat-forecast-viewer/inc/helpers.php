<?php
/**
 * 描画の小物（枠色・バッジ・メータ・数値整形・CSS/フォント読み込み等）
 *
 * boat-forecast-viewer.php から機械的に切り出したもの。中身は変えていない。
 */
if (!defined('ABSPATH')) exit;

function boat_forecast_viewer_favicon_href() {
    return BOAT_FORECAST_VIEWER_URL . 'assets/boat-favicon.svg';
}

function boat_forecast_viewer_render_favicon() {
    $href = esc_url(boat_forecast_viewer_favicon_href());
    echo '<link rel="icon" type="image/svg+xml" href="' . $href . '">' . "\n";
    echo '<link rel="shortcut icon" href="' . $href . '">' . "\n";
    echo '<link rel="apple-touch-icon" href="' . $href . '">' . "\n";
}
/*
 * この3つのフックは管理画面・ログイン画面・テーマ側のページにしか効かない。
 * 本プラグインの5ページ（single / archive / review / accuracy / player）は
 * wp_head() を呼ばず自前で <head> を組み立てているため、フック経由では
 * ファビコンが出ない。各 <head> 内で boat_forecast_viewer_render_favicon() を
 * 直接呼んでいる（boat_forecast_viewer_font_links() の出力の直前）。
 *
 * 注: 行コメント（//）の中に PHP の閉じタグを書くと、コメント内であっても
 *     そこで PHP モードが終了してしまう。この手の説明はブロックコメントで書くこと。
 */
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

/**
 * Phase 13: tiny inline SVG sparkline polyline.
 */
function boat_forecast_viewer_render_sparkline($values, $width = 80, $height = 24, $stroke = 'currentColor') {
    $nums = [];
    foreach ((array) $values as $v) {
        if (is_numeric($v)) $nums[] = (float) $v;
    }
    $w = (int) $width;
    $h = (int) $height;
    if (count($nums) === 0) {
        return sprintf('<svg class="bfv-spark" width="%d" height="%d" aria-hidden="true"></svg>', $w, $h);
    }
    $min = min($nums);
    $max = max($nums);
    if ($max == $min) { $max = $min + 1.0; }
    $pad = 2;
    $n = count($nums);
    $pts = [];
    foreach ($nums as $i => $v) {
        $x = ($n === 1) ? ($w / 2) : ($pad + ($i / ($n - 1)) * ($w - 2 * $pad));
        $y = $h - $pad - (($v - $min) / ($max - $min)) * ($h - 2 * $pad);
        $pts[] = sprintf('%.1f,%.1f', $x, $y);
    }
    return sprintf(
        '<svg class="bfv-spark" width="%d" height="%d" viewBox="0 0 %d %d" aria-hidden="true" preserveAspectRatio="none">'
        . '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>'
        . '</svg>',
        $w, $h, $w, $h, esc_attr(implode(' ', $pts)), esc_attr($stroke)
    );
}

/**
 * Phase 13: classify a venue row against a chip filter (all / curated / today).
 */
function boat_forecast_viewer_match_filter($venue, $filter, $today_ymd) {
    if ($filter === 'curated') {
        // 2026-08-15: 主指標の変更に伴い基準を張り替え。旧基準(順位一致20%)は
        // 順位一致率が実測6%前後のため事実上ほぼ発火しない死んだ条件だった。
        // 回収率があれば回収率100%超、無ければ買い目的中25%以上を「厳選」とする。
        if (isset($venue['roi_avg']) && $venue['roi_avg'] !== null) {
            return $venue['roi_avg'] >= 100.0;
        }
        return isset($venue['hit_any_avg']) && $venue['hit_any_avg'] !== null && $venue['hit_any_avg'] >= 25.0;
    }
    if ($filter === 'today') {
        return isset($venue['latest_date']) && (string) $venue['latest_date'] === (string) $today_ymd;
    }
    return true;
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
        1 => ['#ffffff', '#222222', '#9a9a9a'],
        2 => ['#111111', '#ffffff', '#111111'],
        3 => ['#d73030', '#ffffff', '#d73030'],
        4 => ['#2f6fd6', '#ffffff', '#2f6fd6'],
        5 => ['#f0d44c', '#222222', '#b8960f'],
        6 => ['#4aa35c', '#ffffff', '#4aa35c'],
    ];
    return isset($map[$waku]) ? $map[$waku] : ['#eef3ff', '#222222', '#c8d4f0'];
}

function boat_forecast_viewer_render_waku_name($waku, $name, $is_female, $size = 'md', $reg_no = '') {
    list($bg, $fg, $border) = boat_forecast_viewer_waku_colors($waku);
    $female = !empty($is_female) ? '<span class="bfv-female">♥</span>' : '';
    $size = in_array($size, ['sm', 'md', 'lg'], true) ? $size : 'md';
    // 氏名の空白を半角1個に正規化（全角スペース・連続 → " "、前後トリム）
    $name = preg_replace('/[\x{3000}\s]+/u', ' ', (string) $name);
    $name = trim($name);
    $reg_no = preg_replace('/\D/', '', (string) $reg_no);
    $cell = sprintf(
        '<span class="bfv-waku-name-cell is-%s"><span class="bfv-waku-band" style="background:%s;color:%s;border-color:%s;"><span class="bfv-waku-band-num">%s</span></span><span class="bfv-waku-name">%s%s</span></span>',
        esc_attr($size),
        esc_attr($bg),
        esc_attr($fg),
        esc_attr($border),
        esc_html((string) $waku),
        $female,
        esc_html($name)
    );
    // Phase 24: reg_no が判明していれば選手別ページへリンク
    if ($reg_no !== '' && $name !== '') {
        $url = esc_url(home_url('/player/' . $reg_no . '/'));
        return '<a class="bfv-waku-name-link" href="' . $url . '">' . $cell . '</a>';
    }
    return $cell;
}

/**
 * Phase 12-c: テーブル行内で「順 / 艇 / 選手名」を独立 td として返す。
 * $mark が null の場合は「順」td を出さない（「艇 / 選手名」の2 td）。
 * 「艇」td に枠色を background-color として直接適用 → 自動的に row 全高の縦帯になる。
 */
function boat_forecast_viewer_render_waku_tds($waku, $name, $is_female, $reg_no = '', $mark = null) {
    list($bg, $fg, $border) = boat_forecast_viewer_waku_colors($waku);
    $female = !empty($is_female) ? '<span class="bfv-female">♥</span>' : '';
    $name = preg_replace('/[\x{3000}\s]+/u', ' ', (string) $name);
    $name = trim($name);
    $reg_no = preg_replace('/\D/', '', (string) $reg_no);

    $name_html = $female . esc_html($name);
    if ($reg_no !== '' && $name !== '') {
        $name_html = '<a class="bfv-waku-name-link" href="' . esc_url(home_url('/player/' . $reg_no . '/')) . '">' . $name_html . '</a>';
    }

    $band_style = sprintf('background:%s;color:%s;', esc_attr($bg), esc_attr($fg));

    $out = '';
    if ($mark !== null) {
        $out .= '<td class="bfv-rank-td"><span class="bfv-rank-mark">' . esc_html((string) $mark) . '</span></td>';
    }
    $out .= '<td class="bfv-band-td" style="' . $band_style . '"><span class="bfv-band-num">' . esc_html((string) $waku) . '</span></td>';
    $out .= '<td class="bfv-name-td">' . $name_html . '</td>';
    return $out;
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
 * assets/css/*.css を <style> の中へ展開する。
 *
 * なぜ link rel=stylesheet ではないか:
 *   この5ページは wp_head() を呼ばず自前で head を組むため wp_enqueue_style() が効かない。
 *   加えて、まずは「出力バイト列を変えない」ことを優先している。配信方式の変更は
 *   分割が安定してから独立に判断する。
 *
 * 改行の扱い（ここが肝）:
 *   各ファイルの末尾改行を落として連結し、最後に改行を1つだけ出す。
 *   分割前は PHP が閉じタグ直後の改行を1つ食っていたため、common の末尾 } と
 *   次のセレクタが同じ行に出力されていた。この関数はその出力を再現する。
 *   6URL の本番HTMLと突き合わせてバイト一致を確認済み。
 *
 * 読めないファイルは黙って飛ばす（そのページが無スタイルになるだけで fatal にしない）。
 */
function boat_forecast_viewer_css(...$names) {
    foreach ($names as $name) {
        $path = BOAT_FORECAST_VIEWER_DIR . '/assets/css/' . $name . '.css';
        if (is_readable($path)) {
            echo rtrim(file_get_contents($path), "\n");
        }
    }
    echo "\n";
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
