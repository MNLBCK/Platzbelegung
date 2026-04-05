<?php

declare(strict_types=1);

const FUSSBALL_DE_BASE = 'https://www.fussball.de';
const DATA_DIR = __DIR__ . '/data';
const LATEST_SNAPSHOT = DATA_DIR . '/latest.json';
const CONFIG_FILE = __DIR__ . '/config.yaml';
const VERSION_FILE = __DIR__ . '/VERSION';
const BUILD_META_FILE = __DIR__ . '/BUILD_META.json';
const APP_REPOSITORY_URL = 'https://github.com/MNLBCK/Platzbelegung';
const APP_RELEASES_URL = APP_REPOSITORY_URL . '/releases/tag/';

function isHeadRequest(): bool
{
    return (($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'HEAD');
}

function jsonResponse($data, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    if (isHeadRequest()) {
        return;
    }
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}

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

function loadLatestSnapshot(): ?array
{
    if (!is_file(LATEST_SNAPSHOT)) return null;
    $raw = file_get_contents(LATEST_SNAPSHOT);
    if ($raw === false) return null;
    $data = json_decode($raw, true);
    return is_array($data) ? $data : null;
}

function loadConfig(): ?array
{
    if (!is_file(CONFIG_FILE)) return null;
    $cmd = 'python3 -c ' . escapeshellarg('import yaml, json, sys; print(json.dumps(yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}))') . ' ' . escapeshellarg(CONFIG_FILE);
    $out = shell_exec($cmd);
    if ($out === null) return null;
    $parsed = json_decode($out, true);
    return is_array($parsed) ? $parsed : null;
}

function loadAppVersion(): string
{
    if (!is_file(VERSION_FILE)) {
        return 'dev';
    }
    $raw = trim((string)file_get_contents(VERSION_FILE));
    return $raw !== '' ? $raw : 'dev';
}

function formatFileMTime(?string $path): ?string
{
    if (!$path || !is_file($path)) {
        return null;
    }
    $mtime = filemtime($path);
    if ($mtime === false) {
        return null;
    }
    return gmdate(DATE_ATOM, $mtime);
}

function loadBuildMeta(): array
{
    if (!is_file(BUILD_META_FILE)) {
        return [];
    }
    $raw = file_get_contents(BUILD_META_FILE);
    if ($raw === false) {
        return [];
    }
    $parsed = json_decode($raw, true);
    return is_array($parsed) ? $parsed : [];
}

function loadAppMeta(): array
{
    $baseVersion = loadAppVersion();
    $buildMeta = loadBuildMeta();
    $snapshot = loadLatestSnapshot();
    $snapshotGeneratedAt = is_array($snapshot) ? ($snapshot['generated_at'] ?? null) : null;

    $displayVersion = trim((string)($buildMeta['displayVersion'] ?? $baseVersion));
    if ($displayVersion === '') {
        $displayVersion = $baseVersion;
    }

    $releaseVersion = trim((string)($buildMeta['releaseVersion'] ?? $baseVersion));
    if ($releaseVersion === '') {
        $releaseVersion = $baseVersion;
    }

    $repositoryUrl = trim((string)($buildMeta['repositoryUrl'] ?? APP_REPOSITORY_URL));
    if ($repositoryUrl === '') {
        $repositoryUrl = APP_REPOSITORY_URL;
    }

    $releaseUrl = trim((string)($buildMeta['releaseUrl'] ?? ''));
    if ($releaseUrl === '') {
        $releaseUrl = $releaseVersion === 'dev' ? $repositoryUrl : APP_RELEASES_URL . rawurlencode($releaseVersion);
    }

    $deployedAt = trim((string)($buildMeta['deployedAt'] ?? ''));
    if ($deployedAt === '') {
        $deployedAt = formatFileMTime(BUILD_META_FILE) ?? formatFileMTime(VERSION_FILE) ?? formatFileMTime(LATEST_SNAPSHOT) ?? '';
    }

    return [
        'version' => $displayVersion,
        'baseVersion' => $baseVersion,
        'releaseVersion' => $releaseVersion,
        'repositoryUrl' => $repositoryUrl,
        'releaseUrl' => $releaseUrl,
        'deployedAt' => $deployedAt !== '' ? $deployedAt : null,
        'snapshotGeneratedAt' => is_string($snapshotGeneratedAt) && $snapshotGeneratedAt !== '' ? $snapshotGeneratedAt : null,
    ];
}

function saveConfig(array $config): bool
{
    $json = json_encode($config, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) return false;
    $python = <<<'PY'
import json, sys, yaml
config = json.loads(sys.argv[1])
with open(sys.argv[2], 'w', encoding='utf-8') as f:
    yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
PY;
    $cmd = 'python3 -c ' . escapeshellarg($python) . ' ' . escapeshellarg($json) . ' ' . escapeshellarg(CONFIG_FILE);
    exec($cmd, $dummy, $exitCode);
    return $exitCode === 0;
}

function httpGet(string $url): string
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
            'timeout' => 15,
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

function parseGameDetail(string $url): array
{
    if ($url === '') return [];
    try {
        $xpath = createXPathFromHtml(httpGet($url));
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

    // If we still don't have logos, try to extract club IDs from links
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
        // Merge extracted club IDs with existing logos
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

    return [
        'homeLogoUrl' => $logos[0] ?? '',
        'guestLogoUrl' => $logos[1] ?? '',
        'result' => $result,
    ];
}

function parseClubMatchplanHtml(string $html): array
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

            // Try to get image from src attribute
            $img = $xpath->evaluate('string(.//img[1]/@src)', $cell);
            if ($img === '') {
                // Fallback to data-src (lazy load)
                $img = $xpath->evaluate('string(.//img[1]/@data-src)', $cell);
            }
            if ($img === '') {
                // Fallback to srcset (responsive images)
                $srcset = $xpath->evaluate('string(.//img[1]/@srcset)', $cell);
                if ($srcset !== '') {
                    $img = preg_split('/\s+/', trim($srcset))[0] ?? '';
                }
            }
            if ($img !== '') return toAbsoluteUrl($img);

            // If no image found, try to extract club/team ID from links
            // Try multiple link patterns for better robustness
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

        $scoreText = normalizeText($xpath->evaluate('string(.//td[contains(@class,"column-score") or contains(@class,"column-result")][1])', $row));
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
        $detail = $gameUrl !== '' ? parseGameDetail($gameUrl) : [];
        if (($homeLogoUrl === '' || $guestLogoUrl === '') && !empty($detail)) {
            $homeLogoUrl = $homeLogoUrl !== '' ? $homeLogoUrl : ($detail['homeLogoUrl'] ?? '');
            $guestLogoUrl = $guestLogoUrl !== '' ? $guestLogoUrl : ($detail['guestLogoUrl'] ?? '');
        }
        if ($scoreText === '' && !empty($detail['result'])) {
            $scoreText = (string)$detail['result'];
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

function getJsonBody(): array
{
    $raw = file_get_contents('php://input');
    if (!$raw) return [];
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/';
parse_str(parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_QUERY) ?: '', $query);

if (($method === 'GET' || $method === 'HEAD') && str_starts_with($uri, '/api/')) {
    if ($uri === '/api/snapshot') {
        $snapshot = loadLatestSnapshot();
        if (!$snapshot) jsonResponse(['error' => 'Kein Snapshot vorhanden. Bitte zuerst "platzbelegung scrape" ausführen.'], 404);
        else jsonResponse($snapshot);
        return;
    }

    if ($uri === '/api/meta') {
        jsonResponse(loadAppMeta());
        return;
    }

    if ($uri === '/api/games') {
        $venueIds = $query['venueId'] ?? null;
        if (!$venueIds) { jsonResponse(['error' => 'venueId parameter required'], 400); return; }
        if (!is_array($venueIds)) $venueIds = [$venueIds];
        foreach ($venueIds as $id) {
            if (!preg_match('/^[A-Za-z0-9_-]+$/', (string)$id)) { jsonResponse(['error' => 'Invalid venue ID format'], 400); return; }
        }
        $snapshot = loadLatestSnapshot();
        if (!$snapshot) { jsonResponse(['error' => 'Kein Snapshot vorhanden. Bitte zuerst "platzbelegung scrape" ausführen.'], 404); return; }
        $games = $snapshot['games'] ?? [];
        $filtered = array_values(array_filter($games, fn($g) => in_array($g['venueId'] ?? '', $venueIds, true)));
        jsonResponse($filtered);
        return;
    }

    if ($uri === '/api/search' || $uri === '/api/search/clubs') {
        $q = trim((string)($query['q'] ?? ''));
        if (mb_strlen($q) < 2) { jsonResponse(['error' => 'Suchbegriff zu kurz (min. 2 Zeichen)'], 400); return; }
        try {
            if ($uri === '/api/search') {
                $url = FUSSBALL_DE_BASE . '/suche/-/suche/' . rawurlencode($q) . '/typ/sportstaette';
                $html = httpGet($url);
                $xp = createXPathFromHtml($html);
                $nodes = $xp->query('//*[contains(@class,"search-result-item") or contains(@class,"result-item")]');
                $venues = [];
                foreach ($nodes as $item) {
                    $href = $xp->evaluate('string(.//a[1]/@href)', $item);
                    $name = normalizeText($xp->evaluate('string(.//a[1])', $item));
                    if ($name === '') $name = normalizeText($xp->evaluate('string(.//*[contains(@class,"title")][1])', $item));
                    $location = normalizeText($xp->evaluate('string(.//*[contains(@class,"location") or contains(@class,"subtitle")][1])', $item));
                    if (preg_match('#/id/([^/]+)#', $href, $m) && $name !== '') {
                        $venues[] = ['id' => $m[1], 'name' => $name, 'location' => $location, 'url' => str_starts_with($href, 'http') ? $href : FUSSBALL_DE_BASE . $href];
                    }
                }
                jsonResponse($venues);
            } else {
                $url = FUSSBALL_DE_BASE . '/suche/-/text/' . rawurlencode($q) . '/restriction/CLUB_AND_TEAM#!/';
                $html = httpGet($url);
                $xp = createXPathFromHtml($html);
                $nodes = $xp->query('//*[@id="club-search-results"]//*[@id="clublist"]//li');
                $clubs = [];
                foreach ($nodes as $item) {
                    $href = $xp->evaluate('string(.//a[contains(@class,"image-wrapper")][1]/@href)', $item);
                    $name = normalizeText($xp->evaluate('string(.//a[contains(@class,"image-wrapper")][1]//*[contains(@class,"name")][1])', $item));
                    $location = normalizeText($xp->evaluate('string(.//a[contains(@class,"image-wrapper")][1]//*[contains(@class,"sub")][1])', $item));
                    $logo = toAbsoluteUrl($xp->evaluate('string(.//a[contains(@class,"image-wrapper")][1]//img[1]/@src)', $item));
                    if (preg_match('~/id/([^/?#]+)~', $href, $m) && $name !== '') {
                        $clubs[] = ['id' => $m[1], 'name' => $name, 'location' => $location, 'logoUrl' => $logo, 'url' => str_starts_with($href, 'http') ? $href : FUSSBALL_DE_BASE . $href];
                    }
                }
                jsonResponse($clubs);
            }
        } catch (Throwable $e) {
            jsonResponse(['error' => 'Fehler bei der Suche'], 502);
        }
        return;
    }

    if ($uri === '/api/club-matchplan') {
        $id = trim((string)($query['id'] ?? ''));
        $dateFrom = (string)($query['dateFrom'] ?? '');
        $dateTo = (string)($query['dateTo'] ?? '');
        $matchType = isset($query['matchType']) ? (int)$query['matchType'] : 1;
        $max = isset($query['max']) ? (int)$query['max'] : 100;
        if ($id === '') { jsonResponse(['error' => 'Vereins-ID erforderlich.'], 400); return; }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateFrom)) { jsonResponse(['error' => 'dateFrom muss im Format YYYY-MM-DD angegeben werden.'], 400); return; }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateTo)) { jsonResponse(['error' => 'dateTo muss im Format YYYY-MM-DD angegeben werden.'], 400); return; }
        $max = min(max($max, 1), 200);
        $url = FUSSBALL_DE_BASE . '/ajax.club.matchplan/-/id/' . rawurlencode($id) . '/mode/PAGE/show-filter/false/max/' . rawurlencode((string)$max) . '/datum-von/' . rawurlencode($dateFrom) . '/datum-bis/' . rawurlencode($dateTo) . '/match-type/' . rawurlencode((string)$matchType) . '/show-venues/checked/offset/0';
        try {
            jsonResponse(parseClubMatchplanHtml(httpGet($url)));
        } catch (Throwable $e) {
            jsonResponse(['error' => 'Fehler beim Laden des Vereinsspielplans'], 502);
        }
        return;
    }

    if ($uri === '/api/demo') {
        $today = new DateTimeImmutable('today');
        $entries = [
            [0,10,0,'SV Demo 1','FC Test A','Kreisliga','platz1','Sportplatz 1'],
            [0,12,0,'VfB Demo 2','TSV Test B','Kreispokal','platz1','Sportplatz 1'],
            [1,15,0,'SC Demo 3','FC Test C','A-Junioren','platz1','Sportplatz 1'],
            [2,11,0,'FC Demo 4','SV Test D','Kreisliga','platz2','Sportplatz 2'],
        ];
        $games = array_map(function(array $g) use ($today) {
            [$off,$h,$m,$home,$guest,$comp,$vid,$vname] = $g;
            $d = $today->modify("+$off day")->setTime($h,$m);
            return [
                'venueId'=>$vid,'venueName'=>$vname,'date'=>$d->format('d.m.Y'),'time'=>$d->format('H:i'),
                'homeTeam'=>$home,'guestTeam'=>$guest,'competition'=>$comp,'startDate'=>$d->format(DATE_ATOM),
            ];
        }, $entries);
        jsonResponse($games);
        return;
    }

    if ($uri === '/api/config') {
        $config = loadConfig();
        if (!$config) { jsonResponse(['error' => 'config.yaml nicht gefunden.'], 404); return; }
        jsonResponse(['club'=>$config['club'] ?? (object)[], 'season'=>$config['season'] ?? '', 'venues'=>$config['venues'] ?? []]);
        return;
    }

    jsonResponse(['error' => 'Not found'], 404);
    return;
}

if ($method === 'PUT' && $uri === '/api/config/club') {
    $body = getJsonBody();
    $id = trim((string)($body['id'] ?? ''));
    $name = trim((string)($body['name'] ?? ''));
    if ($id === '') { jsonResponse(['error' => 'Vereins-ID erforderlich.'], 400); return; }
    $config = loadConfig() ?? [];
    $config['club'] = ['id' => $id];
    if ($name !== '') $config['club']['name'] = $name;
    if (!saveConfig($config)) { jsonResponse(['error' => 'Konfiguration konnte nicht gespeichert werden.'], 500); return; }
    jsonResponse(['ok' => true, 'club' => $config['club']]);
    return;
}

if ($method === 'PUT' && $uri === '/api/config/venues') {
    $body = getJsonBody();
    $venues = $body['venues'] ?? null;
    if (!is_array($venues)) { jsonResponse(['error' => 'venues muss ein Array sein.'], 400); return; }
    foreach ($venues as $v) {
        if (!is_array($v)) { jsonResponse(['error' => 'Ungültiges Venue-Objekt.'], 400); return; }
        if (isset($v['aliases']) && !is_array($v['aliases'])) { jsonResponse(['error' => 'aliases muss ein Array sein.'], 400); return; }
        if (isset($v['name_patterns']) && !is_array($v['name_patterns'])) { jsonResponse(['error' => 'name_patterns muss ein Array sein.'], 400); return; }
    }
    $config = loadConfig() ?? [];
    $config['venues'] = array_map(function(array $v) {
        $entry = [];
        foreach (['id','name'] as $k) if (!empty($v[$k])) $entry[$k] = (string)$v[$k];
        if (!empty($v['aliases']) && is_array($v['aliases'])) $entry['aliases'] = array_values(array_map('strval', $v['aliases']));
        if (!empty($v['name_patterns']) && is_array($v['name_patterns'])) $entry['name_patterns'] = array_values(array_map('strval', $v['name_patterns']));
        return $entry;
    }, $venues);
    if (!saveConfig($config)) { jsonResponse(['error' => 'Konfiguration konnte nicht gespeichert werden.'], 500); return; }
    jsonResponse(['ok' => true, 'venues' => $config['venues']]);
    return;
}

if (($method === 'GET' || $method === 'HEAD') && ($uri === '/' || !str_starts_with($uri, '/api/'))) {
    $file = $uri === '/' ? '/index.html' : $uri;
    $path = realpath(__DIR__ . '/public' . $file);
    $public = realpath(__DIR__ . '/public');
    if ($path && $public && str_starts_with($path, $public) && is_file($path)) {
        $ext = pathinfo($path, PATHINFO_EXTENSION);
        $mime = [
            'html'=>'text/html; charset=utf-8',
            'css'=>'text/css; charset=utf-8',
            'js'=>'application/javascript; charset=utf-8',
            'png'=>'image/png',
            'jpg'=>'image/jpeg',
            'jpeg'=>'image/jpeg',
            'svg'=>'image/svg+xml',
            'json'=>'application/json; charset=utf-8',
        ][$ext] ?? 'application/octet-stream';
        header('Content-Type: ' . $mime);
        if (!isHeadRequest()) {
            readfile($path);
        }
        return;
    }
}

jsonResponse(['error' => 'Not found'], 404);
