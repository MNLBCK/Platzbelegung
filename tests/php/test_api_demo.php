<?php

declare(strict_types=1);

function fail(string $message): void
{
    fwrite(STDERR, "FAIL: {$message}\n");
    exit(1);
}

function assert_true(bool $cond, string $message): void
{
    if (!$cond) {
        fail($message);
    }
}

// Simulate an HTTP request to the PHP backend.
$_SERVER['REQUEST_METHOD'] = 'GET';
$_SERVER['REQUEST_URI'] = '/api/demo';

ob_start();
require __DIR__ . '/../../backend.php';
$raw = ob_get_clean();

assert_true(is_string($raw) && $raw !== '', 'Expected non-empty JSON output');

$data = json_decode($raw, true);
if (!is_array($data)) {
    fail('Response is not valid JSON array');
}

assert_true(count($data) === 4, 'Expected 4 demo games');

$requiredKeys = [
    'venueId',
    'venueName',
    'date',
    'time',
    'homeTeam',
    'guestTeam',
    'competition',
    'startDate',
];

foreach ($data as $i => $game) {
    if (!is_array($game)) {
        fail("Game #{$i} is not an object");
    }

    foreach ($requiredKeys as $k) {
        assert_true(array_key_exists($k, $game), "Game #{$i} missing key '{$k}'");
        assert_true(is_string($game[$k]), "Game #{$i} key '{$k}' is not a string");
        assert_true(trim($game[$k]) !== '', "Game #{$i} key '{$k}' is empty");
    }

    $dt = new DateTimeImmutable($game['startDate']);
    assert_true($game['date'] === $dt->format('d.m.Y'), "Game #{$i} date does not match startDate");
    assert_true($game['time'] === $dt->format('H:i'), "Game #{$i} time does not match startDate");
}

fwrite(STDOUT, "OK\n");
