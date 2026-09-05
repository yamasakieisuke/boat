<?php
/**
 * /accuracy/ と /accuracy/<YYYY-Www>/ の描画（boat_forecast_viewer_render_accuracy の本体）。
 *
 * 関数の中から require されるので、呼び出し元のローカル変数がそのまま見える。
 * **単体で読み込んではいけない。**
 *
 * 遅延 require にしているのは爆発半径を1画面に閉じ込めるため。エントリで
 * 全部読むと、このファイルの parse error が全ページと /wp-admin/ まで
 * 巻き込み、管理画面からプラグインを無効化することすらできなくなる。
 */
if (!defined('ABSPATH')) exit;

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
