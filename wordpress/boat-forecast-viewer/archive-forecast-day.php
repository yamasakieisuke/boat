<?php

if (!defined('ABSPATH')) {
    exit;
}

global $wp_query;
boat_forecast_viewer_render_archive($wp_query);
