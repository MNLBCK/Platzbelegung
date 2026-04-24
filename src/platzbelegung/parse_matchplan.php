<?php

declare(strict_types=1);

/**
 * Standalone CLI-Hilfsskript: Vereinsspielplan von fussball.de abrufen und parsen.
 *
 * Diese Datei ist die Version, die mit dem Python-Paket ausgeliefert wird.
 * Sie enthält alle benötigten PHP-Funktionen inline und hat keine externen
 * PHP-Abhängigkeiten (kein require backend.php), damit sie auch in einer
 * installierten wheel/venv-Umgebung funktioniert.
 *
 * Verwendung:
 *   php parse_matchplan.php --id=CLUB_ID --date-from=YYYY-MM-DD --date-to=YYYY-MM-DD [--max=N] [--timeout=N]
 *
 * Ausgabe: JSON-Array der geparsten Spiele auf stdout.
 * Fehler: Meldung auf stderr, Exit-Code != 0.
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(403);
    exit(1);
}

const FUSSBALL_DE_BASE = 'https://www.fussball.de';

// ---------------------------------------------------------------------------
// Helper functions (inlined from backend.php)
// ---------------------------------------------------------------------------

function normalizeText(?string $value): string
{
    $value = $value ?? '';
    $value = str_replace("\u{200b}", '', $value);
    $value = preg_replace('/\s+/u', ' ', $value) ?? $value;
    return trim($value);
}

function toAbsoluteUrl(string $url): string
{
    if ($url === '') return '';
    if (str_starts_with($url, 'http')) return $url;
    if (str_starts_with($url, '//')) return "https:$url";
    if (str_starts_with($url, '/')) return FUSSBALL_DE_BASE . $url;
    return $url;
}

function slugifyVenue(string $value): string
{
    $value = strtolower(normalizeText($value));
    $value = preg_replace('/[^a-z0-9]+/i', '-', $value) ?? $value;
    $value = trim($value, '-');
    return $value !== '' ? $value : 'unbekannte-spielstaette';
}

function httpGet(string $url, int $timeout = 15): string
{
    $headers = [
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language: de-DE,de;q=0.9,en;q=0.5',
    ];

    $ctx = stream_context_create([
        'http' => [
            'method' => 'GET',
            'header' => implode("\r\n", $headers),
            'timeout' => $timeout,
        ],
    ]);

    $resp = @file_get_contents($url, false, $ctx);
    if ($resp === false) {
        throw new RuntimeException("Request failed: $url");
    }
    return $resp;
}

function parseGermanDate(string $dateStr, string $timeStr): ?DateTimeImmutable
{
    if ($dateStr === '') return null;
    if (preg_match('/(\d{2})\.(\d{2})\.(\d{4})/', $dateStr, $m)) {
        [$all, $d, $mth, $y] = $m;
    } elseif (preg_match('/(\d{2})\.(\d{2})\.(\d{2})/', $dateStr, $m)) {
        [$all, $d, $mth, $y] = $m;
        $y = '20' . $y;
    } else {
        return null;
    }

    $hour = '00';
    $min = '00';
    if (preg_match('/(\d{2}):(\d{2})/', $timeStr, $tm)) {
        $hour = $tm[1];
        $min = $tm[2];
    }

    return DateTimeImmutable::createFromFormat('Y-m-d H:i', "$y-$mth-$d $hour:$min") ?: null;
}

function formatGermanDate(DateTimeImmutable $date): string
{
    return $date->format('d.m.Y');
}

function isCancelledGameStatus(string $text): bool
{
    $normalized = mb_strtolower(normalizeText($text), 'UTF-8');
    return in_array($normalized, ['absetzung', 'abgesetzt', 'abgesagt', 'ausgefallen', 'annulliert'], true);
}

function createXPathFromHtml(string $html): DOMXPath
{
    $dom = new DOMDocument();
    libxml_use_internal_errors(true);
    if (function_exists('iconv')) {
        $clean = iconv('UTF-8', 'UTF-8//IGNORE', $html);
        if ($clean !== false) {
            $html = $clean;
        }
    }
    $dom->loadHTML('<?xml encoding="UTF-8">' . $html, LIBXML_NOWARNING | LIBXML_NOERROR);
    libxml_clear_errors();
    return new DOMXPath($dom);
}

function parseGameDetail(string $url, int $timeout = 15): array
{
    if ($url === '') return [];
    try {
        $xpath = createXPathFromHtml(httpGet($url, $timeout));
    } catch (Throwable $e) {
        return [];
    }

    $logos = [];
    foreach ([
        '//*[contains(@class,"team") and contains(@class,"home")]//img[1]',
        '//*[contains(@class,"team") and contains(@class,"guest")]//img[1]',
        '//*[contains(@class,"club") and contains(@class,"home")]//img[1]',
        '//*[contains(@class,"club") and contains(@class,"guest")]//img[1]',
        '(//img[contains(@src,"getLogo") or contains(@data-src,"getLogo")])[1]',
        '(//img[contains(@src,"getLogo") or contains(@data-src,"getLogo")])[2]',
    ] as $expr) {
        $node = $xpath->query($expr)?->item(0);
        if (!$node instanceof DOMElement) continue;
        $src = $node->getAttribute('src') ?: $node->getAttribute('data-src');
        if ($src === '') {
            $srcset = $node->getAttribute('srcset');
            if ($srcset !== '') {
                $src = preg_split('/\s+/', trim($srcset))[0] ?? '';
            }
        }
        if ($src !== '') {
            $logos[] = toAbsoluteUrl($src);
        }
    }
    $logos = array_values(array_unique(array_filter($logos)));

    if (count($logos) < 2) {
        $clubIds = [];
        foreach ([
            'string(//*[contains(@class,"team") and contains(@class,"home")]//a[contains(@href,"/verein/") or contains(@href,"/mannschaft/")][1]/@href)',
            'string(//*[contains(@class,"team") and contains(@class,"guest")]//a[contains(@href,"/verein/") or contains(@href,"/mannschaft/")][1]/@href)',
            'string(//*[contains(@class,"club") and contains(@class,"home")]//a[contains(@href,"/verein/") or contains(@href,"/mannschaft/")][1]/@href)',
            'string(//*[contains(@class,"club") and contains(@class,"guest")]//a[contains(@href,"/verein/") or contains(@href,"/mannschaft/")][1]/@href)',
        ] as $expr) {
            $href = $xpath->evaluate($expr);
            if ($href !== '' && preg_match('~/id/([^/?#]+)~', $href, $m)) {
                $clubIds[] = 'https://www.fussball.de/export.media/-/action/getLogo/format/7/id/' . $m[1];
            }
        }
        foreach ($clubIds as $id) {
            if (!in_array($id, $logos, true)) {
                $logos[] = $id;
            }
        }
    }

    $result = '';
    foreach ([
        'string(//*[contains(@class,"result")][1])',
        'string(//*[contains(@class,"score")][1])',
        'string(//*[contains(@class,"match-result")][1])',
    ] as $expr) {
        $text = normalizeText($xpath->evaluate($expr));
        if ($text !== '' && preg_match('/(\d{1,2}:\d{1,2}|-:-)/', $text, $m)) {
            $result = $m[1];
            break;
        }
    }

    $venueName = '';
    foreach ([
        'string(//a[contains(@class,"location")][1])',
        'string(//*[contains(@class,"match-place")]//*[contains(@class,"location")][1])',
        'string(//*[contains(@class,"game-place")]//*[contains(@class,"location")][1])',
    ] as $expr) {
        $text = normalizeText($xpath->evaluate($expr));
        if ($text !== '') {
            $venueName = $text;
            break;
        }
    }

    $statusText = '';
    foreach ([
        'string(//*[contains(@class,"result")]//*[contains(@class,"info-text")][1])',
        'string(//*[contains(@class,"result")][1])',
        'string(//*[contains(@class,"match-result")]//*[contains(@class,"info-text")][1])',
        'string(//*[contains(@class,"match-result")][1])',
        'string(//*[contains(@class,"score")]//*[contains(@class,"info-text")][1])',
    ] as $expr) {
        $text = normalizeText($xpath->evaluate($expr));
        if ($text !== '') {
            $statusText = $text;
            break;
        }
    }

    return [
        'homeLogoUrl' => $logos[0] ?? '',
        'guestLogoUrl' => $logos[1] ?? '',
        'result' => $result,
        'venueName' => $venueName,
        'statusText' => $statusText,
    ];
}

function parseClubMatchplanHtml(string $html, int $timeout = 15): array
{
    $xpath = createXPathFromHtml($html);

    $rows = $xpath->query('//table[contains(@class,"table-striped")]/tbody/tr');
    $games = [];
    $currentDate = '';
    $currentTime = '';
    $currentCompetition = '';

    foreach ($rows as $i => $row) {
        $class = ' ' . ($row->attributes?->getNamedItem('class')?->nodeValue ?? '') . ' ';

        if (str_contains($class, ' row-headline ') || str_contains($class, ' row-venue ')) {
            continue;
        }

        if (str_contains($class, ' row-competition ')) {
            $dateText = normalizeText($xpath->evaluate('string(.//td[contains(@class,"column-date")][1])', $row));
            $competitionText = normalizeText($xpath->evaluate('string(.//td[contains(@class,"column-team")][1])', $row));
            preg_match('/(\d{2}\.\d{2}\.(?:\d{2}|\d{4}))/', $dateText, $dm);
            preg_match('/(\d{2}:\d{2})/', $dateText, $tm);
            $currentDate = $dm[1] ?? '';
            $currentTime = $tm[1] ?? '';
            $currentCompetition = $competitionText;
            continue;
        }

        $clubCells = $xpath->query('.//td[contains(@class,"column-club")]', $row);
        if (!$clubCells || $clubCells->length < 1 || $currentDate === '') continue;

        $homeCell = $clubCells->item(0);
        $guestCell = $clubCells->item(1);
        $homeTeam = normalizeText($xpath->evaluate('string(.//*[contains(@class,"club-name")][1])', $homeCell) ?: $homeCell?->textContent);
        $guestTeam = normalizeText(($guestCell ? $xpath->evaluate('string(.//*[contains(@class,"club-name") or contains(@class,"info-text")][1])', $guestCell) : '') ?: $guestCell?->textContent);
        if ($homeTeam === '') continue;
        if (preg_match('/^(spielfrei|bye)$/i', $homeTeam) || preg_match('/^(spielfrei|bye)$/i', $guestTeam)) continue;

        $extractLogo = function(?DOMNode $cell) use ($xpath): string {
            if (!$cell) return '';

            $img = $xpath->evaluate('string(.//img[1]/@src)', $cell);
            if ($img === '') {
                $img = $xpath->evaluate('string(.//img[1]/@data-src)', $cell);
            }
            if ($img === '') {
                $srcset = $xpath->evaluate('string(.//img[1]/@srcset)', $cell);
                if ($srcset !== '') {
                    $img = preg_split('/\s+/', trim($srcset))[0] ?? '';
                }
            }
            if ($img !== '') return toAbsoluteUrl($img);

            $hrefs = [
                $xpath->evaluate('string(.//*[contains(@class,"club-wrapper")][1]/@href)', $cell),
                $xpath->evaluate('string(.//*[contains(@class,"club-name")][1]/../@href)', $cell),
                $xpath->evaluate('string(.//a[contains(@href,"/verein/") or contains(@href,"/mannschaft/")][1]/@href)', $cell),
                $xpath->evaluate('string(.//a[1]/@href)', $cell),
            ];

            foreach ($hrefs as $href) {
                if ($href !== '' && preg_match('~/id/([^/?#]+)~', $href, $m)) {
                    return 'https://www.fussball.de/export.media/-/action/getLogo/format/7/id/' . $m[1];
                }
            }

            return '';
        };

        $rawScoreText = normalizeText($xpath->evaluate('string(.//td[contains(@class,"column-score") or contains(@class,"column-result")][1])', $row));
        if (isCancelledGameStatus($rawScoreText)) {
            continue;
        }

        $scoreText = $rawScoreText;
        if ($scoreText !== '' && !preg_match('/^(\d{1,2}:\d{2}|\d{2}:\d{2})$/', $scoreText)) {
            if (preg_match('/(\d{1,2}:\d{1,2}|-:-)/', $scoreText, $sm)) {
                $scoreText = $sm[1];
            }
        } else {
            $scoreText = '';
        }

        $gameUrl = toAbsoluteUrl((string)($xpath->evaluate('string(.//a[contains(normalize-space(.),"Zum Spiel")][1]/@href)', $row) ?: ''));
        if ($gameUrl === '') {
            $gameUrl = toAbsoluteUrl((string)($xpath->evaluate('string(.//a[contains(@href,"/spiel/")][1]/@href)', $row) ?: ''));
        }

        $venueName = '';
        for ($j = $i + 1; $j < $rows->length; $j++) {
            $next = $rows->item($j);
            $nextClass = ' ' . ($next->attributes?->getNamedItem('class')?->nodeValue ?? '') . ' ';
            if (str_contains($nextClass, ' row-competition ')) break;
            if (str_contains($nextClass, ' row-venue ')) {
                $venueName = normalizeText($xpath->evaluate('string(.//td[@colspan="3"][1])', $next) ?: $next->textContent);
                break;
            }
        }

        $parsedDate = parseGermanDate($currentDate, $currentTime);
        if (!$parsedDate) continue;

        $homeLogoUrl = $extractLogo($homeCell);
        $guestLogoUrl = $extractLogo($guestCell);
        $detail = $gameUrl !== '' ? parseGameDetail($gameUrl, $timeout) : [];
        if (($homeLogoUrl === '' || $guestLogoUrl === '') && !empty($detail)) {
            $homeLogoUrl = $homeLogoUrl !== '' ? $homeLogoUrl : ($detail['homeLogoUrl'] ?? '');
            $guestLogoUrl = $guestLogoUrl !== '' ? $guestLogoUrl : ($detail['guestLogoUrl'] ?? '');
        }
        if ($scoreText === '' && !empty($detail['result'])) {
            $scoreText = (string)$detail['result'];
        }
        if ($venueName === '' && !empty($detail['venueName'])) {
            $venueName = normalizeText((string)$detail['venueName']);
        }
        if (!empty($detail['statusText']) && isCancelledGameStatus((string)$detail['statusText'])) {
            continue;
        }

        $games[] = [
            'venueId' => slugifyVenue($venueName),
            'venueName' => $venueName,
            'date' => formatGermanDate($parsedDate),
            'time' => $currentTime,
            'homeTeam' => $homeTeam,
            'homeLogoUrl' => $homeLogoUrl,
            'guestTeam' => $guestTeam,
            'guestLogoUrl' => $guestLogoUrl,
            'competition' => $currentCompetition,
            'result' => $scoreText,
            'gameUrl' => $gameUrl,
            'startDate' => $parsedDate->format(DATE_ATOM),
        ];
    }

    return $games;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

$opts = getopt('', ['id:', 'date-from:', 'date-to:', 'max:', 'timeout:']);

$id       = trim((string)($opts['id'] ?? ''));
$dateFrom = trim((string)($opts['date-from'] ?? ''));
$dateTo   = trim((string)($opts['date-to'] ?? ''));
$max      = min(max((int)($opts['max'] ?? 100), 1), 200);
$timeout  = max(1, (int)($opts['timeout'] ?? 15));

if ($id === '' || $dateFrom === '' || $dateTo === '') {
    fwrite(STDERR, "Fehler: --id, --date-from und --date-to sind erforderlich.\n");
    fwrite(STDERR, "Verwendung: php parse_matchplan.php --id=CLUB_ID --date-from=YYYY-MM-DD --date-to=YYYY-MM-DD [--timeout=N]\n");
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
    $html  = httpGet($url, $timeout);
    $games = parseClubMatchplanHtml($html, $timeout);
    echo json_encode($games, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
    exit(0);
} catch (Throwable $e) {
    fwrite(STDERR, sprintf(
        "Fehler beim Abrufen/Parsen für Verein '%s' (%s – %s): %s\n",
        $id, $dateFrom, $dateTo, $e->getMessage()
    ));
    exit(1);
}
