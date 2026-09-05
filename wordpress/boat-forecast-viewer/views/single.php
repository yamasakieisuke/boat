<?php
/**
 * /race/<venue>-<date>/ の描画（boat_forecast_viewer_render_single の本体・最大の画面）。
 *
 * 関数の中から require されるので $payload / $post がそのまま見える。
 * **単体で読み込んではいけない。**
 *
 * 遅延 require にしているのは爆発半径を1画面に閉じ込めるため。エントリで
 * 全部読むと、このファイルの parse error が全ページと /wp-admin/ まで
 * 巻き込み、管理画面からプラグインを無効化することすらできなくなる。
 */
if (!defined('ABSPATH')) exit;

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
<?php boat_forecast_viewer_doc_open(esc_html(get_the_title($post)), 'single'); ?>
<body>
<?php
$single_venue_slug = get_post_meta($post->ID, 'venue_slug', true);
$single_section = 'RACE';
if ($single_venue_slug) { $single_section .= '.' . strtoupper($single_venue_slug); }
if ($date) { $single_section .= ' / ' . $date; }
boat_forecast_viewer_render_nav('single', $single_section);
?>
<div class="bfv-shell">
    <section class="bfv-hero">
        <div class="bfv-hero-head">
            <h1 class="bfv-hero-title">
                <span class="bfv-hero-venue"><?php echo esc_html($venue); ?></span>
                <span class="bfv-hero-date"><?php echo esc_html($date); ?></span>
            </h1>
            <div class="bfv-hero-status">
                <?php echo boat_forecast_viewer_render_badge($has_exhibition, '展示'); ?>
                <?php echo boat_forecast_viewer_render_badge($has_odds, 'オッズ'); ?>
            </div>
        </div>
        <div class="bfv-hero-meta">
            <?php $publish_stage = (string) get_post_meta($post->ID, 'publish_stage', true); ?>
            <?php if ($publish_stage !== '') : ?>
                <span class="bfv-hero-stat">
                    <span class="bfv-hero-stat-label">Stage</span>
                    <span class="bfv-hero-stat-value"><?php echo esc_html($publish_stage); ?></span>
                </span>
            <?php endif; ?>
            <span class="bfv-hero-stat">
                <span class="bfv-hero-stat-label">Races</span>
                <span class="bfv-hero-stat-value"><?php echo esc_html((string) count($races)); ?>R</span>
            </span>
            <?php if ($updated !== '') : ?>
                <span class="bfv-hero-stat">
                    <span class="bfv-hero-stat-label">Updated</span>
                    <span class="bfv-hero-stat-value"><?php echo esc_html($updated); ?></span>
                </span>
            <?php endif; ?>
            <?php if (!empty($payload['review_summary'])) : ?>
                <a class="bfv-hero-jump" href="#review">振り返り ↓</a>
            <?php endif; ?>
        </div>
        <?php if ($status_note) : ?>
            <div class="bfv-note"><?php echo esc_html($status_note); ?></div>
        <?php endif; ?>
    </section>

    <?php
    // Phase 14: 12R flash list data prep + top-confidence race for 本命 TOP panel.
    $top_race = null;
    foreach ($races as $__r) {
        $c = is_numeric($__r['confidence'] ?? null) ? (float) $__r['confidence'] : 0.0;
        $tc = $top_race && is_numeric($top_race['confidence'] ?? null) ? (float) $top_race['confidence'] : -1.0;
        if ($c > $tc) $top_race = $__r;
    }
    ?>
    <section class="bfv-grid">
        <div class="bfv-flash" id="bfv-summary">
            <div class="bfv-flash-head">
                <div>
                    <h2>12R 早見表</h2>
                    <p class="bfv-flash-sub"><?php echo count($races); ?> races · tap to detail</p>
                </div>
                <div class="bfv-flash-toggles">
                    <span class="bfv-flash-toggle<?php echo $has_exhibition ? ' is-on' : ''; ?>">展示</span>
                    <span class="bfv-flash-toggle<?php echo $has_odds ? ' is-on' : ''; ?>">オッズ</span>
                </div>
            </div>
            <ol class="bfv-flash-list">
                <?php foreach ($races as $race):
                    $rn = (string) ($race['race_no'] ?? '');
                    $main_combo = '';
                    $main_odds = null;
                    $main_bets = (isset($race['main_bets']) && is_array($race['main_bets']))
                        ? $race['main_bets']
                        : (!empty($race['main_bet']) ? [['combo' => $race['main_bet']]] : []);
                    foreach ($main_bets as $b) {
                        if (!empty($b['combo'])) {
                            $main_combo = (string) $b['combo'];
                            if (isset($b['odds']) && is_numeric($b['odds'])) $main_odds = (float) $b['odds'];
                            break;
                        }
                    }
                    $conf_v = is_numeric($race['confidence'] ?? null) ? (int) round((float) $race['confidence']) : 0;
                    $conf_l = (string) ($race['confidence_label'] ?? 'low');
                ?>
                <li class="bfv-flash-row">
                    <a class="bfv-flash-link" href="#race-<?php echo esc_attr($rn); ?>">
                        <span class="bfv-flash-r"><?php echo esc_html($rn); ?>R</span>
                        <span class="bfv-flash-time"><?php echo esc_html((string) ($race['start_time'] ?? '')); ?></span>
                        <span class="bfv-flash-combo"><?php echo esc_html($main_combo !== '' ? $main_combo : '—'); ?></span>
                        <span class="bfv-flash-conf is-conf-<?php echo esc_attr($conf_l); ?>">
                            <span class="bfv-flash-bar"><span style="width:<?php echo esc_attr((string) max(0, min(100, $conf_v))); ?>%"></span></span>
                            <span class="bfv-flash-pct"><?php echo $conf_v > 0 ? esc_html((string) $conf_v) . '%' : '—'; ?></span>
                        </span>
                        <span class="bfv-flash-odds">
                            <?php if ($main_odds !== null) : ?>×<?php echo esc_html(number_format($main_odds, 1)); ?><?php else : ?>—<?php endif; ?>
                            <?php if (!empty($race['is_rough'])) : ?><span class="bfv-flash-tag">荒れ</span><?php endif; ?>
                        </span>
                    </a>
                </li>
                <?php endforeach; ?>
            </ol>
        </div>

        <aside class="bfv-pick-top">
            <div class="bfv-pick-head">
                <?php if ($top_race && !empty($top_race['race_no'])) : ?>
                    <a class="bfv-pick-race" href="#race-<?php echo esc_attr((string) $top_race['race_no']); ?>">
                        <span class="bfv-pick-rno"><?php echo esc_html((string) $top_race['race_no']); ?>R</span>
                        <?php if (!empty($top_race['race_type'])) : ?>
                            <span class="bfv-pick-type"><?php echo esc_html((string) $top_race['race_type']); ?></span>
                        <?php endif; ?>
                        <span class="bfv-pick-time"><?php echo esc_html((string) ($top_race['start_time'] ?? '')); ?></span>
                    </a>
                <?php endif; ?>
                <span class="bfv-pick-label">本命 · Top</span>
            </div>
            <?php if ($top_race) :
                $pick_groups = [
                    ['label' => '本番', 'class' => 'is-main', 'bets' => (isset($top_race['main_bets']) && is_array($top_race['main_bets'])) ? $top_race['main_bets'] : (!empty($top_race['main_bet']) ? [['combo' => $top_race['main_bet']]] : [])],
                    ['label' => '対抗', 'class' => 'is-sub',  'bets' => (isset($top_race['sub_bets']) && is_array($top_race['sub_bets']))   ? $top_race['sub_bets']  : (!empty($top_race['sub_bet'])  ? [['combo' => $top_race['sub_bet']]]  : [])],
                    ['label' => '穴',   'class' => 'is-long', 'bets' => (isset($top_race['longshot_bets']) && is_array($top_race['longshot_bets'])) ? $top_race['longshot_bets'] : (!empty($top_race['longshot_bet']) ? [['combo' => $top_race['longshot_bet']]] : [])],
                ];
                $top_conf_l = (string) ($top_race['confidence_label'] ?? 'low');
                $top_conf_v = is_numeric($top_race['confidence'] ?? null) ? (int) round((float) $top_race['confidence']) : 0;
            ?>
                <div class="bfv-pick-body">
                    <?php foreach ($pick_groups as $g):
                        $has_any = false;
                        foreach ($g['bets'] as $__b) { if (!empty($__b['combo'])) { $has_any = true; break; } }
                        if (!$has_any) continue;
                    ?>
                        <div class="bfv-pick-group <?php echo esc_attr($g['class']); ?>">
                            <span class="bfv-pick-kind"><?php echo esc_html($g['label']); ?></span>
                            <div class="bfv-pick-bets">
                                <?php foreach ($g['bets'] as $b): if (empty($b['combo'])) continue; ?>
                                    <span class="bfv-pick-bet"><?php echo esc_html((string) $b['combo']); ?><?php if (!empty($b['odds']) && is_numeric($b['odds'])): ?><small>×<?php echo esc_html(number_format((float) $b['odds'], 1)); ?></small><?php endif; ?></span>
                                <?php endforeach; ?>
                            </div>
                        </div>
                    <?php endforeach; ?>
                </div>
                <div class="bfv-pick-foot">
                    <span class="bfv-pick-conf is-conf-<?php echo esc_attr($top_conf_l); ?>">信頼度 <?php echo esc_html((string) $top_conf_v); ?>%</span>
                    <?php if (!empty($top_race['is_rough'])) : ?><span class="bfv-flash-tag">荒れ</span><?php endif; ?>
                </div>
            <?php else : ?>
                <div class="bfv-pick-empty">予想データ準備中</div>
            <?php endif; ?>
        </aside>
    </section>

    <section class="bfv-races">
        <?php foreach ($races as $race) :
            $r_conf_v = is_numeric($race['confidence'] ?? null) ? (int) round((float) $race['confidence']) : 0;
            $r_conf_l = (string) ($race['confidence_label'] ?? 'low');
            $r_rno = (string) ($race['race_no'] ?? '');
        ?>
            <article class="bfv-card" id="race-<?php echo esc_attr($r_rno); ?>">
                <header class="bfv-race-hero">
                    <div class="bfv-race-hero-left">
                        <span class="bfv-race-num"><?php echo esc_html($r_rno); ?>R</span>
                        <span class="bfv-race-sep">·</span>
                        <span class="bfv-race-time"><?php echo esc_html((string) ($race['start_time'] ?? '')); ?></span>
                    </div>
                    <div class="bfv-race-hero-right">
                        <span class="bfv-race-conf is-conf-<?php echo esc_attr($r_conf_l); ?>">信頼 <?php echo esc_html((string) $r_conf_v); ?>%</span>
                        <?php if (!empty($race['is_rough'])) : ?>
                            <span class="bfv-race-rough">荒れ</span>
                        <?php endif; ?>
                    </div>
                </header>
                <div class="bfv-weather" aria-label="環境情報">
                    <div class="bfv-weather-cell">
                        <span class="bfv-weather-label">Stage</span>
                        <span class="bfv-weather-value<?php echo empty($race['race_type']) ? ' is-null' : ''; ?>"><?php echo esc_html(!empty($race['race_type']) ? (string) $race['race_type'] : '—'); ?></span>
                    </div>
                    <div class="bfv-weather-cell">
                        <span class="bfv-weather-label">Tide</span>
                        <span class="bfv-weather-value<?php echo empty($race['tide_status']) ? ' is-null' : ''; ?>"><?php echo esc_html(!empty($race['tide_status']) ? (string) $race['tide_status'] : '—'); ?></span>
                    </div>
                    <div class="bfv-weather-cell">
                        <span class="bfv-weather-label">Wind</span>
                        <span class="bfv-weather-value is-null">—</span>
                    </div>
                    <div class="bfv-weather-cell">
                        <span class="bfv-weather-label">Temp</span>
                        <span class="bfv-weather-value is-null">—</span>
                    </div>
                </div>
                <div class="bfv-bets">
                    <section class="bfv-betbox is-main">
                        <strong>本線</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['main_bets']) && is_array($race['main_bets']) ? $race['main_bets'] : [['combo' => ($race['main_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds">×<?php echo esc_html(number_format((float) $bet['odds'], 1)); ?></span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox is-sub">
                        <strong>対抗</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['sub_bets']) && is_array($race['sub_bets']) ? $race['sub_bets'] : [['combo' => ($race['sub_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds">×<?php echo esc_html(number_format((float) $bet['odds'], 1)); ?></span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox is-long">
                        <strong>穴</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['longshot_bets']) && is_array($race['longshot_bets']) ? $race['longshot_bets'] : [['combo' => ($race['longshot_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds">×<?php echo esc_html(number_format((float) $bet['odds'], 1)); ?></span><?php endif; ?></span>
                                <?php endif; ?>
                            <?php endforeach; ?>
                        </div>
                    </section>
                    <section class="bfv-betbox is-cover">
                        <strong>押さえ</strong>
                        <div class="bfv-bet-list">
                            <?php foreach ((isset($race['cover_bets']) && is_array($race['cover_bets']) ? $race['cover_bets'] : [['combo' => ($race['cover_bet'] ?? '')]]) as $bet) : ?>
                                <?php if (!empty($bet['combo'])) : ?>
                                    <span class="bfv-bet"><?php echo esc_html((string) $bet['combo']); ?><?php if (!empty($bet['odds'])) : ?><span class="bfv-odds">×<?php echo esc_html(number_format((float) $bet['odds'], 1)); ?></span><?php endif; ?></span>
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
                <?php /* Phase 19: 予算別買い目セクション */ ?>
                <?php if (!empty($race['budget_plans']) && is_array($race['budget_plans'])) : ?>
                    <div class="bfv-budget-section">
                        <h4>Budget · 予算別買い目</h4>
                        <?php foreach ($race['budget_plans'] as $plan) :
                            $trig_ok = !empty($plan['no_trigarami']);
                            $min_profit = (int) ($plan['min_profit'] ?? 0);
                            $exp_profit = (int) ($plan['expected_profit'] ?? 0);
                        ?>
                            <div class="bfv-budget-box">
                                <div class="bfv-budget-head">
                                    <span class="bfv-budget-amount"><?php echo esc_html(number_format((int) ($plan['budget'] ?? 0))); ?><small>円</small></span>
                                    <span class="bfv-budget-strategy"><?php echo esc_html((string) ($plan['strategy_name'] ?? '配分案')); ?></span>
                                    <span class="bfv-budget-status <?php echo $trig_ok ? 'bfv-budget-ok' : 'bfv-budget-ng'; ?>"><?php echo $trig_ok ? 'トリガミ回避' : '回避不可'; ?></span>
                                </div>
                                <div class="bfv-budget-metrics">
                                    <span><span class="bfv-budget-metric-label">Worst</span><?php echo esc_html(number_format($min_profit)); ?>円</span>
                                    <span><span class="bfv-budget-metric-label">Expected</span><?php echo esc_html(number_format($exp_profit)); ?>円</span>
                                </div>
                                <?php if (!empty($plan['strategy_description'])) : ?>
                                    <div class="bfv-budget-note"><?php echo esc_html((string) $plan['strategy_description']); ?></div>
                                <?php endif; ?>
                                <?php if (!empty($plan['rows']) && is_array($plan['rows'])) : ?>
                                    <table class="bfv-budget-table">
                                        <tr><th>種別</th><th>買い目</th><th>配分</th><th>オッズ</th><th>的中収支</th></tr>
                                        <?php foreach ($plan['rows'] as $brow) : ?>
                                            <tr>
                                                <td><?php echo esc_html((string) ($brow['label'] ?? '')); ?></td>
                                                <td><?php echo esc_html((string) ($brow['combo'] ?? '')); ?></td>
                                                <td><?php echo esc_html(number_format((int) ($brow['stake'] ?? 0))); ?>円</td>
                                                <td>×<?php echo esc_html(number_format((float) ($brow['odds'] ?? 0), 1)); ?></td>
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
                                    <tr><th>艇</th><th>選手名</th><th>状態</th><th>コメント</th><th>判定根拠</th></tr>
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
                                            <?php echo boat_forecast_viewer_render_waku_tds($cp['waku'] ?? '', $cp['name'] ?? '', !empty($cp['is_female']), $cp['reg_no'] ?? ''); ?>
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
                                <tr><th>艇</th><th>選手名</th><th>展示T</th><th>チルト</th><th>進入</th><th>前走ST</th><th>前走着</th><th>評価</th></tr>
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
                                        <?php echo boat_forecast_viewer_render_waku_tds($exrow['waku'] ?? '', $exrow['name'] ?? '', false, $exrow['reg_no'] ?? ''); ?>
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

                <?php /* v5.21: 福岡オリジナル展示（一周/まわり足/直線） */ ?>
                <?php if (!empty($race['original_exhibition_section']['rows']) && is_array($race['original_exhibition_section']['rows'])) : ?>
                    <section class="bfv-detail-block">
                        <h4>オリジナル展示（一周・まわり足・直線）</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table bfv-orig-tenji">
                                <tr>
                                    <th>艇</th>
                                    <th>選手名</th>
                                    <th>一周</th>
                                    <th>まわり足</th>
                                    <th>直線</th>
                                    <th>評価</th>
                                </tr>
                                <?php foreach ($race['original_exhibition_section']['rows'] as $orow) : ?>
                                    <?php
                                        $lap_rank = $orow['lap_rank'] ?? null;
                                        $turn_rank = $orow['turn_rank'] ?? null;
                                        $straight_rank = $orow['straight_rank'] ?? null;
                                        $cell_cls = function ($rank) {
                                            if ($rank === 1) return 'is-rank1';
                                            if ($rank === 2) return 'is-rank2';
                                            return '';
                                        };
                                        $fmt = function ($v) {
                                            if ($v === null || $v === '') return '-';
                                            return esc_html(number_format((float) $v, 2));
                                        };
                                        $eval_v = $orow['evaluation'] ?? null;
                                    ?>
                                    <tr>
                                        <?php echo boat_forecast_viewer_render_waku_tds($orow['waku'] ?? '', $orow['name'] ?? '', !empty($orow['is_female']), $orow['reg_no'] ?? ''); ?>
                                        <td class="<?php echo esc_attr($cell_cls($lap_rank)); ?>"><?php echo $fmt($orow['lap_time'] ?? null); ?><?php if ($lap_rank === 1) echo '<span class="bfv-rank-mark">★</span>'; ?></td>
                                        <td class="<?php echo esc_attr($cell_cls($turn_rank)); ?>"><?php echo $fmt($orow['turn_time'] ?? null); ?><?php if ($turn_rank === 1) echo '<span class="bfv-rank-mark">★</span>'; ?></td>
                                        <td class="<?php echo esc_attr($cell_cls($straight_rank)); ?>"><?php echo $fmt($orow['straight_time'] ?? null); ?><?php if ($straight_rank === 1) echo '<span class="bfv-rank-mark">★</span>'; ?></td>
                                        <td><?php echo $eval_v !== null ? esc_html((string) $eval_v) : '-'; ?></td>
                                    </tr>
                                <?php endforeach; ?>
                            </table>
                        </div>
                        <?php if (!empty($race['original_exhibition_section']['source'])) : ?>
                            <div class="bfv-source-note">出典: <?php echo esc_html($race['original_exhibition_section']['source']); ?></div>
                        <?php endif; ?>
                    </section>
                <?php endif; ?>

                <?php if (!empty($race['top_picks']) && is_array($race['top_picks'])) : ?>
                    <table class="bfv-pick-table has-rank">
                        <?php foreach ($race['top_picks'] as $pick) :
                            $mark = (string) ($pick['mark'] ?? '');
                            $score_raw = isset($pick['score']) && is_numeric($pick['score']) ? (float) $pick['score'] : null;
                        ?>
                            <tr>
                                <?php echo boat_forecast_viewer_render_waku_tds(
                                    $pick['waku'] ?? '',
                                    $pick['name'] ?? '',
                                    !empty($pick['is_female']),
                                    $pick['reg_no'] ?? '',
                                    $mark
                                ); ?>
                                <td class="bfv-pick-meta-td">
                                    <?php if (!empty($pick['grade'])) : ?>
                                        <?php echo boat_forecast_viewer_render_grade($pick['grade']); ?>
                                    <?php endif; ?>
                                    <?php if (!empty($pick['comment_label'])) : ?>
                                        <span>コメント <?php echo esc_html((string) $pick['comment_label']); ?></span>
                                    <?php endif; ?>
                                    <?php if (!empty($pick['exhibition_time'])) : ?>
                                        <span>展示 <?php echo esc_html((string) $pick['exhibition_time']); ?></span>
                                    <?php endif; ?>
                                </td>
                                <td class="bfv-pick-note-td">
                                    <?php if (!empty($pick['comment_text'])) : ?>
                                        <?php echo esc_html((string) $pick['comment_text']); ?>
                                    <?php endif; ?>
                                </td>
                                <td class="bfv-pick-score-td">
                                    <small>Score</small>
                                    <?php echo $score_raw !== null ? esc_html(number_format($score_raw * 100, 1)) : '—'; ?>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </table>
                <?php endif; ?>
                <?php if (!empty($race['detailed_predictions']) && is_array($race['detailed_predictions'])) : ?>
                    <?php $display_rows = boat_forecast_viewer_sort_rows_by_waku($race['detailed_predictions']); ?>
                    <section class="bfv-detail-block">
                        <h4>実データ</h4>
                        <div class="bfv-detail-wrap">
                            <table class="bfv-detail-table sticky-name-table has-rank">
                                <tr>
                                    <th>順</th>
                                    <th>艇</th>
                                    <th>選手名</th>
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
                                    <?php echo boat_forecast_viewer_render_waku_tds($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female']), $row['reg_no'] ?? '', boat_forecast_viewer_mark_for_rank($row['rank'] ?? 0)); ?>
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
                                    <th>選手名</th>
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
                                    <?php echo boat_forecast_viewer_render_waku_tds($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female']), $row['reg_no'] ?? ''); ?>
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
                                    <th>選手名</th>
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
                                    <?php echo boat_forecast_viewer_render_waku_tds($row['waku'] ?? '', $row['name'] ?? '', !empty($row['is_female']), $row['reg_no'] ?? ''); ?>
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
                    <strong>レース的中</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_bet_any_pct'] ?? '-')); ?>%</div>
                    <div class="bfv-review-sub">3連単買い目8点のいずれかが的中</div>
                </div>
                <div class="bfv-review-card is-primary">
                    <strong>本命</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_honmei_pct'] ?? '-')); ?>%</div>
                    <div class="bfv-review-sub">本命4点のいずれかが3連単的中</div>
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
                <div class="bfv-review-card">
                    <strong>1着的中</strong>
                    <div class="bfv-review-value"><?php echo esc_html((string) ($review['hit_1st_pct'] ?? '-')); ?>%</div>
                    <div class="bfv-review-sub">本命1番手の頭が一致（参考）</div>
                </div>
            </div>
            <?php
            // Phase 16: 12R Timeline — classify each race row by verdict text in the last cell.
            $timeline_rows = (!empty($review['race_table']['rows']) && is_array($review['race_table']['rows'])) ? $review['race_table']['rows'] : [];
            if (!empty($timeline_rows)) :
                $verdict_class = function ($txt) {
                    $s = (string) $txt;
                    if (strpos($s, '3連単一致') !== false) return 'is-order';
                    if (strpos($s, '3連複') !== false)   return 'is-box';
                    if (strpos($s, '買い目的中') !== false || strpos($s, '的中') !== false && strpos($s, '不') === false) return 'is-hit';
                    if (strpos($s, '不的中') !== false) return 'is-miss';
                    return 'is-miss';
                };
            ?>
            <div class="bfv-timeline">
                <div class="bfv-timeline-head">
                    <h4>12R · Timeline</h4>
                    <div class="bfv-timeline-legend">
                        <span><span class="bfv-legend-dot is-hit"></span>HIT</span>
                        <span><span class="bfv-legend-dot is-order"></span>ORDER</span>
                        <span><span class="bfv-legend-dot is-box"></span>BOX</span>
                        <span><span class="bfv-legend-dot is-miss"></span>MISS</span>
                    </div>
                </div>
                <div class="bfv-timeline-row">
                    <?php foreach ($timeline_rows as $tr_row):
                        $cells = is_array($tr_row) ? array_values($tr_row) : [];
                        if (empty($cells)) continue;
                        $rno = (string) ($cells[0] ?? '');
                        $verdict_txt = (string) end($cells);
                        $cls = $verdict_class($verdict_txt);
                    ?>
                        <span class="bfv-timeline-pill <?php echo esc_attr($cls); ?>" title="<?php echo esc_attr($rno . ': ' . $verdict_txt); ?>">
                            <?php echo esc_html(preg_replace('/\D/', '', $rno) ?: $rno); ?>
                        </span>
                    <?php endforeach; ?>
                </div>
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
