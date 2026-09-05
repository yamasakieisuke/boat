<?php
/**
 * /race/ と /race/<venue>/ の描画（boat_forecast_viewer_render_archive の本体）。
 *
 * 関数の中から require されるので、呼び出し元のローカル変数（$query 等）が
 * そのまま見える。**単体で読み込んではいけない。**
 *
 * なぜ遅延 require か: エントリで全部読むと、このファイルの parse error が
 * 全ページと /wp-admin/ まで巻き込み、管理画面からプラグインを無効化する
 * ことすらできなくなる。呼ばれた時だけ読めば、壊れても該当ページだけで済む。
 */
if (!defined('ABSPATH')) exit;

    $posts = $query->posts;
    $venue_slug = get_query_var('bfv_venue');
    $venue_map = boat_forecast_viewer_venue_map();
    $venue_name = isset($venue_map[$venue_slug]) ? $venue_map[$venue_slug] : strtoupper((string) $venue_slug);
    $venues = boat_forecast_viewer_collect_archive_items();
    ?>
<?php boat_forecast_viewer_doc_open('Race Forecast Archive', 'archive'); ?>
<body>
<?php
$archive_section = $venue_slug ? 'VENUE.' . strtoupper($venue_slug) : 'FORECAST.INDEX';
boat_forecast_viewer_render_nav('archive', $archive_section);
?>
<div class="bfva-shell">
    <?php if ($venue_slug) : ?>
        <header class="bfva-hero">
            <h1><?php echo esc_html($venue_name); ?></h1>
            <p>予想一覧</p>
        </header>
    <?php else :
        // Phase 13: 30-day HIT RATE KPI + sparkline
        $global_kpi = boat_forecast_viewer_compute_global_kpi($venues, 30);
        $today_ymd = current_time('Y-m-d');
        $filter_key = isset($_GET['filter']) ? (string) $_GET['filter'] : 'all';
        if (!in_array($filter_key, ['all', 'curated', 'today'], true)) { $filter_key = 'all'; }
        $total_venues = count($venues);
        $count_curated = 0;
        $count_today = 0;
        foreach ($venues as $_v) {
            if (boat_forecast_viewer_match_filter($_v, 'curated', $today_ymd)) $count_curated++;
            if (boat_forecast_viewer_match_filter($_v, 'today', $today_ymd)) $count_today++;
        }
        $archive_base = get_post_type_archive_link('forecast_day') ?: home_url('/race/');
    ?>
        <header class="bfva-hero">
            <div class="bfva-hero-kpi">
                <span class="bfva-hero-label">Last 30d · 3連単 Hit Rate</span>
                <?php if ($global_kpi['hit_rate'] !== null) : ?>
                    <span class="bfva-hero-value"><?php echo esc_html(number_format($global_kpi['hit_rate'], 1)); ?><small>%</small></span>
                <?php else : ?>
                    <span class="bfva-hero-value is-null">—</span>
                <?php endif; ?>
                <span class="bfva-hero-meta"><?php echo (int) $global_kpi['race_days']; ?>R verified · <?php echo $total_venues; ?> venues</span>
            </div>
            <?php echo boat_forecast_viewer_render_sparkline($global_kpi['sparkline'], 140, 40); ?>
        </header>
        <div class="bfva-chips">
            <a class="bfva-chip<?php echo $filter_key === 'all' ? ' is-active' : ''; ?>" href="<?php echo esc_url($archive_base); ?>">All <span><?php echo $total_venues; ?></span></a>
            <a class="bfva-chip<?php echo $filter_key === 'curated' ? ' is-active' : ''; ?>" href="<?php echo esc_url(add_query_arg('filter', 'curated', $archive_base)); ?>">厳選済 <span><?php echo $count_curated; ?></span></a>
            <a class="bfva-chip<?php echo $filter_key === 'today' ? ' is-active' : ''; ?>" href="<?php echo esc_url(add_query_arg('filter', 'today', $archive_base)); ?>">本日 <span><?php echo $count_today; ?></span></a>
        </div>
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
            if (!boat_forecast_viewer_match_filter($venue, $filter_key, $today_ymd)) continue;
            $latest_link = !empty($venue['latest_link']) ? $venue['latest_link'] : home_url('/race/' . $venue['slug'] . '/');
            $items = isset($venue['items']) && is_array($venue['items']) ? $venue['items'] : [];
            $hit_any_avg = isset($venue['hit_any_avg']) ? $venue['hit_any_avg'] : null;
            $roi_avg     = isset($venue['roi_avg'])     ? $venue['roi_avg']     : null;
            $spark_values = isset($venue['sparkline']) ? $venue['sparkline'] : [];
        ?>
            <article class="bfva-card">
                <div class="bfva-card-head">
                    <div class="bfva-card-head-left">
                        <h2><a class="bfva-card-link" href="<?php echo esc_url($latest_link); ?>"><?php echo esc_html($venue['name']); ?></a></h2>
                        <span class="bfva-card-slug">/<?php echo esc_html($venue['slug']); ?></span>
                    </div>
                    <span class="bfva-card-date"><?php echo esc_html($venue['latest_date']); ?></span>
                </div>

                <div class="bfva-card-kpi">
                    <div class="bfva-kpi-col is-primary">
                        <?php if ($hit_any_avg !== null) : ?>
                            <span class="bfva-kpi-num"><?php echo esc_html(number_format($hit_any_avg, 1)); ?><small>%</small></span>
                        <?php else : ?>
                            <span class="bfva-kpi-num is-null">—</span>
                        <?php endif; ?>
                        <span class="bfva-kpi-sub">的中率</span>
                    </div>
                    <div class="bfva-kpi-col">
                        <?php if ($roi_avg !== null) : ?>
                            <span class="bfva-kpi-num"><?php echo esc_html(number_format($roi_avg, 1)); ?><small>%</small></span>
                        <?php else : ?>
                            <span class="bfva-kpi-num is-null">—</span>
                        <?php endif; ?>
                        <span class="bfva-kpi-sub">回収率</span>
                    </div>
                    <?php echo boat_forecast_viewer_render_sparkline($spark_values, 120, 28); ?>
                </div>

                <div class="bfva-card-list">
                    <?php foreach ($items as $item):
                        $row_hit = ($item['hit_any'] !== null)
                            ? number_format($item['hit_any'], 1) . '%'
                            : (!empty($item['has_review']) ? '振返済' : '予想のみ');
                    ?>
                        <a class="bfva-card-row<?php echo !empty($item['has_review']) ? ' has-review' : ''; ?>"
                           href="<?php echo esc_url(!empty($item['has_review']) ? ($item['link'] . '#review') : $item['link']); ?>"
                           title="<?php echo esc_attr((string) ($item['title'] ?? '')); ?>">
                            <span class="bfva-card-row-dot" aria-hidden="true"></span>
                            <span class="bfva-card-row-date"><?php echo esc_html((string) $item['date']); ?></span>
                            <span class="bfva-card-row-hit"><?php echo esc_html($row_hit); ?></span>
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
