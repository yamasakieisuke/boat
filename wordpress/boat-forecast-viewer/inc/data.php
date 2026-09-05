<?php
/**
 * データ読み込みと集計（payload / accuracy / players / アーカイブ集約）
 *
 * boat-forecast-viewer.php から機械的に切り出したもの。中身は変えていない。
 */
if (!defined('ABSPATH')) exit;

function boat_forecast_viewer_collect_archive_items() {
    $posts = get_posts([
        'post_type' => 'forecast_day',
        'post_status' => 'publish',
        'numberposts' => -1,
        'orderby' => 'date',
        'order' => 'DESC',
        'update_post_meta_cache' => false,
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
        // Phase 13: per-item hit rates from review_summary for KPI aggregation.
        // 2026-08-15: 主指標を hit_3tan(順位一致) → hit_bet_any(3連単の買い目的中) へ。
        // 順位一致は「買っていない買い目が当たっていたか」を数えており、実運用と乖離していた。
        $hit_any = null;
        $roi = null;
        if (!empty($payload['review_summary']) && is_array($payload['review_summary'])) {
            $rs = $payload['review_summary'];
            if (isset($rs['hit_bet_any_pct']) && is_numeric($rs['hit_bet_any_pct'])) {
                $hit_any = (float) $rs['hit_bet_any_pct'];
            }
            if (isset($rs['roi_pct']) && is_numeric($rs['roi_pct'])) {
                $roi = (float) $rs['roi_pct'];
            }
        }
        $venues[$venue_slug]['items'][] = [
            'title' => get_the_title($post),
            'link' => get_permalink($post),
            'date' => $race_date,
            'has_review' => !empty($payload['review_summary']),
            'hit_any' => $hit_any,
            'roi' => $roi,
        ];
        unset($payload);
        wp_cache_delete($post->ID, 'post_meta');
    }

    foreach ($venues as $slug => $venue) {
        usort($venue['items'], function ($a, $b) {
            return strcmp((string) $b['date'], (string) $a['date']);
        });
        // per-venue KPI averages（主指標は3連単の買い目的中率）
        $ha = [];
        $ro = [];
        foreach ($venue['items'] as $it) {
            if ($it['hit_any'] !== null) $ha[] = $it['hit_any'];
            if (isset($it['roi']) && $it['roi'] !== null) $ro[] = $it['roi'];
        }
        $venue['hit_any_avg'] = $ha ? array_sum($ha) / count($ha) : null;
        $venue['roi_avg']     = $ro ? array_sum($ro) / count($ro) : null;
        // Sparkline: last 8 reviewed items in chronological order (old -> new).
        $venue['sparkline'] = array_slice(array_reverse($ha), -8);
        $venue['all_items'] = $venue['items'];
        $venue['items'] = array_slice($venue['items'], 0, 4);
        $venues[$slug] = $venue;
    }

    uasort($venues, function ($a, $b) {
        return strcmp((string) $b['latest_date'], (string) $a['latest_date']);
    });

    return $venues;
}

/**
 * Phase 13: compute global archive KPI for the last N days.
 * @param array $venues output of boat_forecast_viewer_collect_archive_items()
 * @param int $window_days
 * @return array ['hit_rate', 'sparkline' (chronological), 'race_days', 'window_days']
 */
function boat_forecast_viewer_compute_global_kpi($venues, $window_days = 30) {
    $cutoff = date('Y-m-d', strtotime('-' . max(1, (int) $window_days) . ' days'));
    $flat = [];
    foreach ($venues as $venue) {
        $pool = isset($venue['all_items']) ? $venue['all_items'] : (isset($venue['items']) ? $venue['items'] : []);
        foreach ($pool as $it) {
            if (!isset($it['hit_any']) || $it['hit_any'] === null) continue;
            if ((string) $it['date'] < $cutoff) continue;
            $flat[] = $it;
        }
    }
    usort($flat, function ($a, $b) { return strcmp((string) $a['date'], (string) $b['date']); });
    $nums = [];
    foreach ($flat as $it) $nums[] = (float) $it['hit_any'];
    return [
        'window_days' => (int) $window_days,
        'hit_rate'    => $nums ? array_sum($nums) / count($nums) : null,
        'sparkline'   => $nums,
        'race_days'   => count($nums),
    ];
}

function boat_forecast_viewer_load_payload($post_id) {
    $raw = get_post_meta($post_id, 'forecast_payload', true);
    if (!is_string($raw) || $raw === '') {
        return [];
    }
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function boat_forecast_viewer_load_accuracy_data($week_key = '') {
    $dir = BOAT_FORECAST_VIEWER_DIR . '/data/accuracy';
    $idx_path = $dir . '/index.json';
    $index = null;
    if (file_exists($idx_path)) {
        $raw = file_get_contents($idx_path);
        $idx = json_decode($raw, true);
        if (is_array($idx)) {
            $index = $idx;
        }
    }
    $week_key = (string) $week_key;
    if ($week_key === '' && $index && !empty($index['weeks'])) {
        $week_key = (string) $index['weeks'][0]['week'];
    }
    $week_data = null;
    if ($week_key !== '') {
        $wpath = $dir . '/' . preg_replace('/[^A-Za-z0-9\-]/', '', $week_key) . '.json';
        if (file_exists($wpath)) {
            $raw = file_get_contents($wpath);
            $d = json_decode($raw, true);
            if (is_array($d)) {
                $week_data = $d;
            }
        }
    }
    return ['index' => $index, 'week' => $week_data];
}

function boat_forecast_viewer_load_player_data($reg_no = '') {
    $dir = BOAT_FORECAST_VIEWER_DIR . '/data/players';
    $reg_no = preg_replace('/\D/', '', (string) $reg_no);
    $index = null;
    $idx_path = $dir . '/index.json';
    if (file_exists($idx_path)) {
        $raw = file_get_contents($idx_path);
        $i = json_decode($raw, true);
        if (is_array($i)) {
            $index = $i;
        }
    }
    $player = null;
    if ($reg_no !== '') {
        $p = $dir . '/' . $reg_no . '.json';
        if (file_exists($p)) {
            $raw = file_get_contents($p);
            $d = json_decode($raw, true);
            if (is_array($d)) {
                $player = $d;
            }
        }
    }
    return ['index' => $index, 'player' => $player, 'reg_no' => $reg_no];
}
