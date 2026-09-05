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
}

function boat_forecast_viewer_render_archive($query) {
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
}

function boat_forecast_viewer_render_review() {
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
}


function boat_forecast_viewer_render_accuracy() {
    $req_week = (string) get_query_var('bfv_week');
    $bundle = boat_forecast_viewer_load_accuracy_data($req_week);
    $idx = $bundle['index'];
    $w   = $bundle['week'];
    $section_code = $w ? ('ACCURACY.' . strtoupper(str_replace('-', '.', $w['week']))) : 'ACCURACY';
    ?>
<?php boat_forecast_viewer_doc_open('精度ダッシュボード — ボートレース予想', 'accuracy'); ?>
<body>
<?php boat_forecast_viewer_render_nav('accuracy', $section_code); ?>
<div class="bfac-shell">

<?php if (!$w) : ?>
    <section class="bfac-empty">
        まだ精度レポートが生成されていません。<br>
        <code style="font-family: var(--bfv-font-mono); font-size: 12px; color: var(--bfv-accent);">python3 scripts/verify.py --report weekly</code>
        を実行すると、本ページにデータが反映されます。
    </section>
<?php else :
    $o = isset($w['overall']) ? $w['overall'] : [];
    $diff = isset($w['diff_prev_week']) ? $w['diff_prev_week'] : [];
    $delta_class = function ($v) {
        if ($v === null) return 'is-flat';
        if ($v > 0) return 'is-up';
        if ($v < 0) return 'is-down';
        return 'is-flat';
    };
    $delta_str = function ($v) {
        if ($v === null) return '—';
        $sign = ($v > 0) ? '+' : '';
        return $sign . $v;
    };
    $kpis = [
        ['label' => '買い目的中率',   'k' => 'hit_bet_any_pct',  'n' => 'hit_bet_any'],
        ['label' => '本命的中率',     'k' => 'hit_honmei_pct',   'n' => 'hit_honmei'],
        ['label' => '回収率',         'k' => 'roi_pct',          'n' => null],
        ['label' => '頭的中率',       'k' => 'hit_1st_pct',      'n' => 'hit_1st'],
    ];
?>
    <section class="bfac-hero">
        <span class="bfac-hero-kicker">📈 ACCURACY · <?php echo esc_html($w['week']); ?></span>
        <h1 class="bfac-hero-title">週次精度レポート</h1>
        <p class="bfac-hero-meta">
            <?php echo esc_html($w['date_from']); ?> 〜 <?php echo esc_html($w['date_to']); ?>
            ・ 総レース <?php echo (int) ($o['total_races'] ?? 0); ?>R
            ・ 対象会場 <?php echo (int) ($o['venues_with_data'] ?? 0); ?>
        </p>
        <div class="bfac-hero-grid">
        <?php foreach ($kpis as $k):
            $val = isset($o[$k['k']]) ? $o[$k['k']] : 0;
            $hit = ($k['n'] !== null && isset($o[$k['n']])) ? $o[$k['n']] : null;
            $tot = (int) ($o['total_races'] ?? 0);
            $d   = isset($diff[$k['k']]) ? $diff[$k['k']] : null;
        ?>
            <div class="bfac-kpi">
                <span class="bfac-kpi-label"><?php echo esc_html($k['label']); ?></span>
                <span class="bfac-kpi-value"><?php echo esc_html($val); ?>%</span>
                <span class="bfac-kpi-sub"><?php
                    echo ($hit === null) ? '100円/点' : ((int) $hit . '/' . (int) $tot);
                ?></span>
                <span class="bfac-kpi-delta <?php echo $delta_class($d); ?>">
                    前週比 <?php echo esc_html($delta_str($d)); ?>
                </span>
            </div>
        <?php endforeach; ?>
        </div>
    </section>

    <?php if (!empty($w['by_venue'])): ?>
    <section class="bfac-section">
        <div class="bfac-section-head">
            <h2 class="bfac-section-title">会場別ランキング</h2>
            <span class="bfac-section-note">買い目的中率順</span>
        </div>
        <table class="bfac-table">
            <thead>
                <tr>
                    <th>順</th>
                    <th>会場</th>
                    <th>R数</th>
                    <th>買い目的中%</th>
                    <th>回収率%</th>
                    <th>頭的中%</th>
                    <th>平均着順</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach ($w['by_venue'] as $i => $v):
                $rank = $i + 1;
                $cls = $rank <= 3 ? ' is-top' : '';
            ?>
                <tr>
                    <td><span class="bfac-rank<?php echo $cls; ?>"><?php echo $rank; ?></span></td>
                    <td class="bfac-name"><?php echo esc_html($v['name']); ?></td>
                    <td><?php echo (int) $v['n']; ?></td>
                    <td><?php echo esc_html($v['hit_bet_any_pct']); ?>%</td>
                    <td><?php echo esc_html($v['roi_pct'] ?? 0); ?>%</td>
                    <td><?php echo esc_html($v['hit_1st_pct']); ?>%</td>
                    <td><?php echo esc_html($v['avg_rank']); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
    <?php endif; ?>

    <?php if (!empty($w['by_pattern'])): ?>
    <section class="bfac-section">
        <div class="bfac-section-head">
            <h2 class="bfac-section-title">セオリーパターン別</h2>
            <span class="bfac-section-note">発動 vs 採用 / 的中率</span>
        </div>
        <table class="bfac-table">
            <thead>
                <tr>
                    <th>パターン</th>
                    <th>発動R</th>
                    <th>発動的中%</th>
                    <th>採用R</th>
                    <th>採用的中%</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach ($w['by_pattern'] as $name => $p): ?>
                <tr>
                    <td class="bfac-name"><?php echo esc_html($name); ?></td>
                    <td><?php echo (int) ($p['triggered'] ?? 0); ?></td>
                    <td><?php echo esc_html($p['triggered_hit_pct'] ?? 0); ?>%</td>
                    <td><?php echo (int) ($p['applied'] ?? 0); ?></td>
                    <td><?php echo esc_html($p['applied_hit_pct'] ?? 0); ?>%</td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
    <?php endif; ?>

    <?php if (!empty($w['by_series_band'])): ?>
    <section class="bfac-section">
        <div class="bfac-section-head">
            <h2 class="bfac-section-title">シリーズ走数帯別</h2>
            <span class="bfac-section-note">本命的中率 (今節走数別)</span>
        </div>
        <table class="bfac-table">
            <thead>
                <tr>
                    <th>走数帯</th>
                    <th>n</th>
                    <th>本命的中%</th>
                    <th>平均着順</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach (['0走','1-3走','4-6走','7走+'] as $band):
                if (empty($w['by_series_band'][$band])) continue;
                $d = $w['by_series_band'][$band];
            ?>
                <tr>
                    <td class="bfac-name"><?php echo esc_html($band); ?></td>
                    <td><?php echo (int) ($d['n'] ?? 0); ?></td>
                    <td><?php echo esc_html($d['honmei_hit_pct'] ?? 0); ?>%</td>
                    <td><?php echo esc_html($d['avg_rk'] ?? '—'); ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
    <?php endif; ?>

    <?php if (!empty($w['by_version'])): ?>
    <section class="bfac-section">
        <div class="bfac-section-head">
            <h2 class="bfac-section-title">バージョン別</h2>
            <span class="bfac-section-note">version 別の指標推移</span>
        </div>
        <table class="bfac-table">
            <thead>
                <tr>
                    <th>version</th>
                    <th>n</th>
                    <th>点数</th>
                    <th>買い目的中%</th>
                    <th>本命%</th>
                    <th>回収率%</th>
                </tr>
            </thead>
            <tbody>
            <?php foreach ($w['by_version'] as $ver => $d): ?>
                <tr>
                    <td class="bfac-name"><?php echo esc_html($ver); ?></td>
                    <td><?php echo (int) ($d['n'] ?? 0); ?></td>
                    <td><?php echo esc_html($d['points'] ?? 0); ?></td>
                    <td><?php echo esc_html($d['hit_bet_any_pct'] ?? 0); ?>%</td>
                    <td><?php echo esc_html($d['hit_honmei_pct'] ?? 0); ?>%</td>
                    <td><?php echo esc_html($d['roi_pct'] ?? 0); ?>%</td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </section>
    <?php endif; ?>
<?php endif; ?>

<?php if ($idx && !empty($idx['weeks']) && count($idx['weeks']) > 0): ?>
    <section class="bfac-section">
        <div class="bfac-section-head">
            <h2 class="bfac-section-title">過去の週次レポート</h2>
            <span class="bfac-section-note">最新 <?php echo count($idx['weeks']); ?> 週</span>
        </div>
        <div class="bfac-week-list">
        <?php foreach ($idx['weeks'] as $row):
            $is_current = $w && (string) $row['week'] === (string) $w['week'];
            $url = esc_url(home_url('/accuracy/' . $row['week'] . '/'));
        ?>
            <a class="bfac-week-row<?php echo $is_current ? ' is-current' : ''; ?>" href="<?php echo $url; ?>">
                <b><?php echo esc_html($row['week']); ?></b>
                <span><?php echo (int) ($row['total_races'] ?? 0); ?>R</span>
                <span>買目 <?php echo esc_html($row['hit_bet_any_pct'] ?? 0); ?>%</span>
                <span class="bfac-week-3tan">回収 <?php echo esc_html($row['roi_pct'] ?? 0); ?>%</span>
                <span>頭 <?php echo esc_html($row['hit_1st_pct'] ?? 0); ?>%</span>
            </a>
        <?php endforeach; ?>
        </div>
    </section>
<?php endif; ?>

</div>
</body>
</html>
<?php
}


function boat_forecast_viewer_render_player() {
    $req_reg_no = (string) get_query_var('bfv_reg_no');
    $bundle = boat_forecast_viewer_load_player_data($req_reg_no);
    $idx    = $bundle['index'];
    $p      = $bundle['player'];
    $reg_no = $bundle['reg_no'];
    $is_top = ($reg_no === '');
    $section_code = $is_top ? 'PLAYER.INDEX' : ('PLAYER.' . $reg_no);
    ?>
<?php boat_forecast_viewer_doc_open(($is_top ? '選手一覧' : ('選手 — ' . esc_html($p['name'] ?? $reg_no))) . ' — ボートレース予想', 'player'); ?>
<body>
<?php boat_forecast_viewer_render_nav('player', $section_code); ?>
<div class="bfp-shell">

<?php if ($is_top) :
    $players = ($idx && !empty($idx['today_players'])) ? $idx['today_players'] : [];
?>
    <section class="bfp-hero">
        <span class="bfp-hero-kicker">👤 PLAYER · <?php echo esc_html($idx['date'] ?? date('Y-m-d')); ?></span>
        <h1 class="bfp-hero-name">本日出走の選手</h1>
        <p class="bfp-hero-meta">
            <?php echo (int) ($idx['today_count'] ?? 0); ?> 名 ・ 五十音順
        </p>
    </section>
    <?php if (!$players) : ?>
        <section class="bfp-empty">
            本日の出走データがまだ揃っていません。<br>
            朝バッチ（09時前後）の取得後に表示されます。
        </section>
    <?php else : ?>
        <section class="bfp-section">
            <div class="bfp-section-head">
                <h2 class="bfp-section-title">出走選手一覧</h2>
                <span class="bfp-section-note">タップで詳細</span>
            </div>
            <div class="bfp-index-grid">
            <?php foreach ($players as $row) :
                $url = esc_url(home_url('/player/' . preg_replace('/\D/', '', $row['reg_no']) . '/'));
                $grade = (string) ($row['grade'] ?? '');
                $grade_cls = ($grade === 'A1' || $grade === 'A2') ? ' is-' . $grade : '';
            ?>
                <a class="bfp-index-card" href="<?php echo $url; ?>">
                    <div>
                        <div class="bfp-index-name"><?php echo esc_html($row['name'] ?? ''); ?></div>
                        <div class="bfp-index-meta">
                            <?php echo esc_html($row['branch'] ?? ''); ?>
                            ・<?php echo esc_html(implode('/', $row['venues'] ?? [])); ?>
                            ・<?php echo (int) ($row['races_today'] ?? 0); ?>R
                        </div>
                    </div>
                    <span class="bfp-index-grade<?php echo $grade_cls; ?>"><?php echo esc_html($grade); ?></span>
                </a>
            <?php endforeach; ?>
            </div>
        </section>
    <?php endif; ?>

<?php elseif (!$p) : ?>
    <section class="bfp-empty">
        選手データが見つかりません（reg_no = <?php echo esc_html($reg_no); ?>）。<br>
        本日出走予定の選手のみページが生成されています。
    </section>
    <a href="<?php echo esc_url(home_url('/player/')); ?>" style="font-family: var(--bfv-font-mono); font-size: 12px; color: var(--bfv-accent);">← 選手一覧へ戻る</a>

<?php else :
    $is_female = ($p['gender'] === 'F');
    $upcoming = isset($p['upcoming_today']) && is_array($p['upcoming_today']) ? $p['upcoming_today'] : [];
    $yearly = isset($p['yearly_waku_stats']) && is_array($p['yearly_waku_stats']) ? $p['yearly_waku_stats'] : [];
    krsort($yearly); // 新しい年から
?>
    <section class="bfp-hero">
        <span class="bfp-hero-kicker">👤 PLAYER · <?php echo esc_html($reg_no); ?></span>
        <h1 class="bfp-hero-name">
            <?php echo esc_html($p['name'] ?? $reg_no); ?>
            <?php if ($is_female) : ?><span class="bfp-female">♥</span><?php endif; ?>
            <span class="bfp-reg-no"><?php echo esc_html($p['name_kana'] ?? ''); ?></span>
        </h1>
        <p class="bfp-hero-meta">
            <?php
                $meta_parts = [];
                if (!empty($p['grade']))      $meta_parts[] = esc_html($p['grade']);
                if (!empty($p['branch']))     $meta_parts[] = '支部 ' . esc_html($p['branch']);
                if (!empty($p['prefecture'])) $meta_parts[] = '出身 ' . esc_html($p['prefecture']);
                echo implode(' ・ ', $meta_parts);
            ?>
        </p>
        <div class="bfp-hero-grid">
            <div class="bfp-kpi">
                <span class="bfp-kpi-label">勝率 (全国)</span>
                <span class="bfp-kpi-value"><?php echo isset($p['win_rate']) ? esc_html($p['win_rate']) : '—'; ?></span>
            </div>
            <div class="bfp-kpi">
                <span class="bfp-kpi-label">能力指数</span>
                <span class="bfp-kpi-value"><?php echo isset($p['ability_index']) ? esc_html($p['ability_index']) : '—'; ?></span>
            </div>
            <div class="bfp-kpi">
                <span class="bfp-kpi-label">優勝回数</span>
                <span class="bfp-kpi-value"><?php echo isset($p['championship_count']) ? esc_html($p['championship_count']) : '—'; ?></span>
            </div>
            <div class="bfp-kpi">
                <span class="bfp-kpi-label">本日</span>
                <span class="bfp-kpi-value"><?php echo count($upcoming); ?>R</span>
            </div>
        </div>
    </section>

    <?php if ($upcoming) : ?>
    <section class="bfp-section">
        <div class="bfp-section-head">
            <h2 class="bfp-section-title">本日の出走予定</h2>
            <span class="bfp-section-note">今節成績付き</span>
        </div>
        <div class="bfp-upcoming-list">
        <?php foreach ($upcoming as $u) :
            $w = (int) ($u['waku'] ?? 0);
            $jcd = (string) ($u['jcd'] ?? '');
            $rno = (int) ($u['race_no'] ?? 0);
            $venue = (string) ($u['venue_name'] ?? '');
            $races = isset($u['series_races']) && is_array($u['series_races']) ? $u['series_races'] : [];
        ?>
            <div class="bfp-upcoming-row">
                <span class="bfp-waku-cell is-w<?php echo $w; ?>"><?php echo $w; ?></span>
                <span class="bfp-upcoming-venue"><?php echo esc_html($venue); ?></span>
                <span class="bfp-series">
                    <?php if ($races) : ?>
                        <?php foreach ($races as $sr) :
                            if (!is_array($sr)) continue;
                            $c = isset($sr['course']) ? (string) $sr['course'] : '?';
                            $rk = isset($sr['rank']) ? (string) $sr['rank'] : '?';
                        ?>
                            <span class="bfp-series-pair"><?php echo esc_html($c); ?>→<?php echo esc_html($rk); ?></span>
                        <?php endforeach; ?>
                    <?php else : ?>
                        <span style="color: var(--bfv-muted); font-size: 10px;">初日／実績なし</span>
                    <?php endif; ?>
                </span>
                <span class="bfp-upcoming-rno"><?php echo $rno; ?>R</span>
            </div>
        <?php endforeach; ?>
        </div>
    </section>
    <?php endif; ?>

    <?php if ($yearly) : ?>
    <section class="bfp-section">
        <div class="bfp-section-head">
            <h2 class="bfp-section-title">年度別 枠別成績</h2>
            <span class="bfp-section-note">2025-03 以降の集計</span>
        </div>
        <?php foreach ($yearly as $year => $waku_stats) :
            // "all" を末尾に
            ksort($waku_stats);
            $waku_keys = array_filter(array_keys($waku_stats), function ($k) { return $k !== 'all'; });
            sort($waku_keys);
            $all = isset($waku_stats['all']) ? $waku_stats['all'] : null;
        ?>
            <h3 style="margin: 14px 0 8px; font-size: 13px; font-family: var(--bfv-font-mono); letter-spacing: 0.06em; color: var(--bfv-ink-sub);">
                <?php echo esc_html($year); ?> 年
                <?php if ($all) : ?>
                    <span style="font-size: 11px; color: var(--bfv-muted);">
                        ・ <?php echo (int) $all['races']; ?>走 ・ 1着率 <?php echo esc_html($all['1st_pct']); ?>%
                    </span>
                <?php endif; ?>
            </h3>
            <table class="bfp-table">
                <thead>
                    <tr>
                        <th>枠</th>
                        <th>走</th>
                        <th>1着%</th>
                        <th>2着%</th>
                        <th>3着%</th>
                        <th>4着%</th>
                        <th>5着%</th>
                        <th>6着%</th>
                        <th>2連%</th>
                        <th>3連%</th>
                    </tr>
                </thead>
                <tbody>
                <?php foreach ($waku_keys as $w) :
                    $d = $waku_stats[$w];
                ?>
                    <tr>
                        <td>
                            <span class="bfp-waku-cell is-w<?php echo (int) $w; ?>"><?php echo esc_html($w); ?></span>
                        </td>
                        <td><?php echo (int) ($d['races'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['1st_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['2nd_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['3rd_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['4th_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['5th_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['6th_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['top2_pct'] ?? 0); ?></td>
                        <td><?php echo esc_html($d['top3_pct'] ?? 0); ?></td>
                    </tr>
                <?php endforeach; ?>
                <?php if ($all) : ?>
                    <tr class="bfp-row-all">
                        <td>合計</td>
                        <td><?php echo (int) $all['races']; ?></td>
                        <td><?php echo esc_html($all['1st_pct']); ?></td>
                        <td><?php echo esc_html($all['2nd_pct']); ?></td>
                        <td><?php echo esc_html($all['3rd_pct']); ?></td>
                        <td><?php echo esc_html($all['4th_pct']); ?></td>
                        <td><?php echo esc_html($all['5th_pct']); ?></td>
                        <td><?php echo esc_html($all['6th_pct']); ?></td>
                        <td><?php echo esc_html($all['top2_pct']); ?></td>
                        <td><?php echo esc_html($all['top3_pct']); ?></td>
                    </tr>
                <?php endif; ?>
                </tbody>
            </table>
        <?php endforeach; ?>
    </section>
    <?php else : ?>
        <section class="bfp-empty">
            この選手の過去成績データがありません（results_csv 範囲外）。
        </section>
    <?php endif; ?>

    <p style="margin-top: 18px; text-align: center;">
        <a href="<?php echo esc_url(home_url('/player/')); ?>" style="font-family: var(--bfv-font-mono); font-size: 12px; color: var(--bfv-accent); text-decoration: none;">← 選手一覧へ戻る</a>
    </p>
<?php endif; ?>

</div>
</body>
</html>
<?php
}


function boat_forecast_viewer_activate() {
    boat_forecast_viewer_add_rewrite_rules();
    flush_rewrite_rules();
}
register_activation_hook(__FILE__, 'boat_forecast_viewer_activate');
