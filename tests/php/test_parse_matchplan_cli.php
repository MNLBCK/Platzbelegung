<?php

declare(strict_types=1);

/**
 * Test für parse_matchplan.php CLI-Skript.
 *
 * Prüft:
 * - Fehlende Argumente → Exit-Code 1, Fehlermeldung auf stderr
 * - Ungültiges Datumsformat → Exit-Code 1
 * - Gültige Argumente → Exit-Code 0 oder 1 bei Netzwerkfehler (kein Live-Test)
 */

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

function run_parse_script(array $args): array
{
    $script = __DIR__ . '/../../parse_matchplan.php';
    $cmd = array_merge(['php', $script], $args);
    $result = proc_open(
        implode(' ', array_map('escapeshellarg', $cmd)),
        [
            0 => ['pipe', 'r'],
            1 => ['pipe', 'w'],
            2 => ['pipe', 'w'],
        ],
        $pipes
    );
    if (!is_resource($result)) {
        fail('Could not start parse_matchplan.php');
    }
    fclose($pipes[0]);
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $exitCode = proc_close($result);
    return ['stdout' => $stdout, 'stderr' => $stderr, 'exitCode' => $exitCode];
}

// Test 1: Keine Argumente → Exit-Code 1 und Fehlermeldung
$result = run_parse_script([]);
assert_true($result['exitCode'] === 1, 'Expected exit code 1 when no args');
assert_true(str_contains($result['stderr'], '--id'), 'Expected --id in error message');

// Test 2: Nur --id → fehlende dateFrom/dateTo → Exit-Code 1
$result = run_parse_script(['--id=TESTCLUB']);
assert_true($result['exitCode'] === 1, 'Expected exit code 1 when dateFrom/dateTo missing');

// Test 3: Ungültiges Datumsformat → Exit-Code 1
$result = run_parse_script([
    '--id=TESTCLUB',
    '--date-from=01.01.2026',  // falsches Format
    '--date-to=31.12.2026',
]);
assert_true($result['exitCode'] === 1, 'Expected exit code 1 for invalid date format');
assert_true(str_contains($result['stderr'], 'YYYY-MM-DD'), 'Expected YYYY-MM-DD in error message');

// Test 4: Gültige Argumente → endet mit Exit-Code 0 (Netzwerk OK) oder 1 (Netzwerkfehler)
// Wir testen nur, dass das Skript startet und keine PHP-Syntaxfehler hat.
// Ohne Live-Netzwerk ist Exit-Code 1 mit Fehlermeldung erwartet.
$result = run_parse_script([
    '--id=00ES8GNAVO00000PVV0AG08LVUPGND5I',
    '--date-from=2026-01-01',
    '--date-to=2026-12-31',
    '--max=5',
]);
// Entweder Exit 0 mit JSON-Ausgabe oder Exit 1 mit Fehlermeldung
$validExit = $result['exitCode'] === 0 || $result['exitCode'] === 1;
assert_true($validExit, 'Expected exit code 0 or 1 for valid args');
if ($result['exitCode'] === 0) {
    $data = json_decode($result['stdout'], true);
    assert_true(is_array($data), 'Expected JSON array output on success');
}

fwrite(STDOUT, "OK\n");
