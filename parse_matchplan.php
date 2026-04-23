<?php

declare(strict_types=1);

/**
 * CLI-Hilfsskript: Vereinsspielplan von fussball.de abrufen und parsen.
 *
 * Dieses Skript ist die einzige Stelle, an der fussball.de-HTML geparst wird.
 * Es nutzt die Parsing-Funktionen aus backend.php und ist die
 * Single Source of Truth für die Spielplan-Normalisierung.
 *
 * Verwendung:
 *   php parse_matchplan.php --id=CLUB_ID --date-from=YYYY-MM-DD --date-to=YYYY-MM-DD [--max=N]
 *
 * Ausgabe: JSON-Array der geparsten Spiele auf stdout.
 * Fehler: Meldung auf stderr, Exit-Code != 0.
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit(1);
}

// Parsing-Funktionen aus dem Backend laden (HTTP-Routing wird dabei übersprungen)
define('PLATZBELEGUNG_CLI_PARSE', true);
require __DIR__ . '/backend.php';

$opts = getopt('', ['id:', 'date-from:', 'date-to:', 'max:']);

$id       = trim((string)($opts['id'] ?? ''));
$dateFrom = trim((string)($opts['date-from'] ?? ''));
$dateTo   = trim((string)($opts['date-to'] ?? ''));
$max      = min(max((int)($opts['max'] ?? 100), 1), 200);

if ($id === '' || $dateFrom === '' || $dateTo === '') {
    fwrite(STDERR, "Fehler: --id, --date-from und --date-to sind erforderlich.\n");
    fwrite(STDERR, "Verwendung: php parse_matchplan.php --id=CLUB_ID --date-from=YYYY-MM-DD --date-to=YYYY-MM-DD\n");
    exit(1);
}

if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateFrom) || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateTo)) {
    fwrite(STDERR, "Fehler: Datumsformat muss YYYY-MM-DD sein.\n");
    exit(1);
}

$url = FUSSBALL_DE_BASE
    . '/ajax.club.matchplan/-/id/' . rawurlencode($id)
    . '/mode/PAGE/show-filter/false/max/' . rawurlencode((string)$max)
    . '/datum-von/' . rawurlencode($dateFrom)
    . '/datum-bis/' . rawurlencode($dateTo)
    . '/match-type/1/show-venues/checked/offset/0';

try {
    $html  = httpGet($url);
    $games = parseClubMatchplanHtml($html);
    echo json_encode($games, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
    exit(0);
} catch (Throwable $e) {
    fwrite(STDERR, 'Fehler beim Abrufen/Parsen: ' . $e->getMessage() . "\n");
    exit(1);
}
