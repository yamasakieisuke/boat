<?php
/**
 * 5ページ共通の <!DOCTYPE> 〜 </head>。
 *
 * この5ページ（single / archive / review / accuracy / player）はテーマを使わず
 * 自前で完結した HTML 文書を返す。<head> の中身は **<title> と読み込むCSS名以外
 * 完全に同一** だったので1箇所にまとめる。
 *
 * ⚠️ wp_head() は呼ばない。呼ぶとテーマや他プラグインの出力が混ざって
 *    レイアウトが変わる。favicon はそのため直接呼んでいる。
 *
 * $title_html はエスケープ済みのHTMLをそのまま出す。呼び出し側が
 * esc_html() を通した文字列を渡す前提（分割前の挙動と同じ）。
 */
if (!defined('ABSPATH')) exit;

function boat_forecast_viewer_doc_open($title_html, $css_page) {
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?php echo $title_html; ?></title>
<?php boat_forecast_viewer_render_favicon(); ?>
<?php echo boat_forecast_viewer_font_links(); ?>
    <style>
<?php boat_forecast_viewer_css('common', $css_page); ?>
    </style>
</head>
<?php
}
