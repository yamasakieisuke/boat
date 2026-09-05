<?php
/**
 * /player/ と /player/<reg_no>/ の描画（boat_forecast_viewer_render_player の本体）。
 *
 * 関数の中から require されるので、呼び出し元のローカル変数がそのまま見える。
 * **単体で読み込んではいけない。**
 *
 * 遅延 require にしているのは爆発半径を1画面に閉じ込めるため。エントリで
 * 全部読むと、このファイルの parse error が全ページと /wp-admin/ まで
 * 巻き込み、管理画面からプラグインを無効化することすらできなくなる。
 */
if (!defined('ABSPATH')) exit;

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
