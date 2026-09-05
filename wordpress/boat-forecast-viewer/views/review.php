<?php
/**
 * /review/ の描画（boat_forecast_viewer_render_review の本体）。
 *
 * 関数の中から require されるので、呼び出し元のローカル変数がそのまま見える。
 * **単体で読み込んではいけない。**
 *
 * 遅延 require にしているのは爆発半径を1画面に閉じ込めるため。エントリで
 * 全部読むと、このファイルの parse error が全ページと /wp-admin/ まで
 * 巻き込み、管理画面からプラグインを無効化することすらできなくなる。
 */
if (!defined('ABSPATH')) exit;

    $posts = get_posts([
        'post_type'    => 'forecast_day',
        'post_status'  => 'publish',
        'numberposts'  => -1,
        'orderby'      => 'date',
        'order'        => 'DESC',
        'update_post_meta_cache' => false,
    ]);

    $all_items        = [];
    $total_races      = 0;
    $weighted_any_sum = 0.0;
    foreach ($posts as $post) {
        $payload = boat_forecast_viewer_load_payload($post->ID);
        if (empty($payload['review_summary']) || !is_array($payload['review_summary'])) {
            unset($payload);
            wp_cache_delete($post->ID, 'post_meta');
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
        unset($payload);
        wp_cache_delete($post->ID, 'post_meta');
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
<?php boat_forecast_viewer_doc_open('振り返り一覧 — ボートレース予想', 'review'); ?>
<body>
<?php boat_forecast_viewer_render_nav('review', 'REVIEW'); ?>
<div class="bfrv-shell">
    <section class="bfrv-hero">
        <span class="bfrv-kicker">振り返り</span>
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
                        $roi_pct   = (float) ($review['roi_pct']         ?? 0);
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
                                    <?php if ($tan_pct > 0) : ?>
                                        <span class="bfrv-pill">3連単 <?php echo esc_html(number_format($tan_pct, 1)); ?>%</span>
                                    <?php endif; ?>
                                    <?php if ($fuku_pct > 0) : ?>
                                        <span class="bfrv-pill">3連複 <?php echo esc_html(number_format($fuku_pct, 1)); ?>%</span>
                                    <?php endif; ?>
                                    <?php if ($first_pct > 0) : ?>
                                        <span class="bfrv-pill">1着 <?php echo esc_html(number_format($first_pct, 1)); ?>%</span>
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
