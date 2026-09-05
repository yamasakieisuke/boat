<?php
/**
 * URLルーティング（rewrite / query_vars / pre_get_posts / template_include）
 *
 * boat-forecast-viewer.php から機械的に切り出したもの。中身は変えていない。
 */
if (!defined('ABSPATH')) exit;

function boat_forecast_viewer_add_rewrite_rules() {
    $venue_pattern = implode('|', array_keys(boat_forecast_viewer_venue_map()));
    add_rewrite_rule('^race/(' . $venue_pattern . ')/?$', 'index.php?post_type=forecast_day&bfv_venue=$matches[1]', 'top');
    add_rewrite_rule('^review/?$', 'index.php?bfv_review=1', 'top');
    add_rewrite_rule('^accuracy/?$', 'index.php?bfv_accuracy=1', 'top');
    add_rewrite_rule('^accuracy/([0-9]{4}-W[0-9]{2})/?$', 'index.php?bfv_accuracy=1&bfv_week=$matches[1]', 'top');
    add_rewrite_rule('^player/?$', 'index.php?bfv_player=1', 'top');
    add_rewrite_rule('^player/([0-9]{4,5})/?$', 'index.php?bfv_player=1&bfv_reg_no=$matches[1]', 'top');
}
add_action('init', 'boat_forecast_viewer_add_rewrite_rules');

function boat_forecast_viewer_query_vars($vars) {
    $vars[] = 'bfv_venue';
    $vars[] = 'bfv_review';
    $vars[] = 'bfv_accuracy';
    $vars[] = 'bfv_week';
    $vars[] = 'bfv_player';
    $vars[] = 'bfv_reg_no';
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
    if (get_query_var('bfv_accuracy')) {
        return BOAT_FORECAST_VIEWER_DIR . '/accuracy-forecast.php';
    }
    if (get_query_var('bfv_player')) {
        return BOAT_FORECAST_VIEWER_DIR . '/player-forecast.php';
    }
    return $template;
}
add_filter('template_include', 'boat_forecast_viewer_template_include');
