<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

function respond(int $status, array $payload): void {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    respond(405, ['ok' => false, 'error' => 'method_not_allowed']);
}

$expectedToken = getenv('BOAT_SYNC_TOKEN') ?: '';
$requestToken = $_SERVER['HTTP_X_BOAT_TOKEN'] ?? '';
if ($expectedToken === '' || !hash_equals($expectedToken, $requestToken)) {
    respond(403, ['ok' => false, 'error' => 'invalid_token']);
}

$raw = file_get_contents('php://input');
try {
    $payload = json_decode($raw ?: '', true, 512, JSON_THROW_ON_ERROR);
} catch (Throwable $e) {
    respond(400, ['ok' => false, 'error' => 'invalid_json', 'message' => $e->getMessage()]);
}

$requiredTop = ['title', 'slug', 'status', 'content', 'acf'];
foreach ($requiredTop as $key) {
    if (!array_key_exists($key, $payload)) {
        respond(400, ['ok' => false, 'error' => 'missing_field', 'field' => $key]);
    }
}

if (!is_array($payload['acf'])) {
    respond(400, ['ok' => false, 'error' => 'invalid_field', 'field' => 'acf']);
}

$requiredAcf = [
    'venue_code',
    'venue_slug',
    'venue_name',
    'race_date',
    'updated_at',
    'publish_stage',
    'has_exhibition',
    'has_odds',
    'status_note',
    'forecast_payload',
];
foreach ($requiredAcf as $key) {
    if (!array_key_exists($key, $payload['acf'])) {
        respond(400, ['ok' => false, 'error' => 'missing_field', 'field' => "acf.$key"]);
    }
}

$wpLoad = dirname(__DIR__) . '/wp-load.php';
if (!file_exists($wpLoad)) {
    respond(500, ['ok' => false, 'error' => 'wp_load_not_found']);
}
require_once $wpLoad;

if (!post_type_exists('forecast_day')) {
    respond(500, ['ok' => false, 'error' => 'post_type_not_found', 'post_type' => 'forecast_day']);
}

$slug = sanitize_title((string) $payload['slug']);
$existing = get_page_by_path($slug, OBJECT, 'forecast_day');
$postarr = [
    'post_type' => 'forecast_day',
    'post_status' => (string) $payload['status'],
    'post_name' => $slug,
    'post_title' => (string) $payload['title'],
    'post_content' => (string) $payload['content'],
];

$action = 'created';
if ($existing instanceof WP_Post) {
    $postarr['ID'] = $existing->ID;
    $postId = wp_update_post(wp_slash($postarr), true);
    $action = 'updated';
} else {
    $postId = wp_insert_post(wp_slash($postarr), true);
}

if (is_wp_error($postId)) {
    respond(500, ['ok' => false, 'error' => 'post_write_failed', 'message' => $postId->get_error_message()]);
}

foreach ($payload['acf'] as $field => $value) {
    if (function_exists('update_field')) {
        update_field($field, $value, $postId);
    } else {
        update_post_meta($postId, $field, $value);
    }
}

$link = get_permalink($postId);
respond(200, [
    'ok' => true,
    'action' => $action,
    'post_id' => $postId,
    'slug' => $slug,
    'link' => $link,
]);
