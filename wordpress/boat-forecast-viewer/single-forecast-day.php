<?php

if (!defined('ABSPATH')) {
    exit;
}

$post = get_queried_object();
if (!($post instanceof WP_Post)) {
    status_header(404);
    exit;
}

$payload = boat_forecast_viewer_load_payload($post->ID);
boat_forecast_viewer_render_single($payload, $post);
