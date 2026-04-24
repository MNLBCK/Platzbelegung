<?php

declare(strict_types=1);

const FUSSBALL_DE_BASE = 'https://www.fussball.de';
const DATA_DIR = __DIR__ . '/data';
const LATEST_SNAPSHOT = DATA_DIR . '/latest.json';
const CONFIG_FILE = __DIR__ . '/config.yaml';
const VERSION_FILE = __DIR__ . '/VERSION';
const BUILD_META_FILE = __DIR__ . '/BUILD_META.json';
const USAGE_STATS_FILE = DATA_DIR . '/club_parse_stats.json';
const SHARED_CONFIGS_FILE = DATA_DIR . '/shared_configs.json';
const STATS_PASSWORD_FILE = __DIR__ . '/.stats_password';
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

function runGitCommand(array $args): string
{
    $cmd = 'git -C ' . escapeshellarg(__DIR__);
    foreach ($args as $arg) {
        $cmd .= ' ' . escapeshellarg((string)$arg);
    }
    $cmd .= ' 2>/dev/null';
    $out = shell_exec($cmd);
    return trim((string)$out);
}

function loadGitVersionMeta(string $preferredReleaseVersion): array
{
    $gitDir = runGitCommand(['rev-parse', '--git-dir']);
    if ($gitDir === '') {
        return [];
    }

    $branch = runGitCommand(['rev-parse', '--abbrev-ref', 'HEAD']);
    $releaseVersion = $preferredReleaseVersion;

    if ($releaseVersion !== '') {
        $tagExists = runGitCommand(['rev-parse', '-q', '--verify', 'refs/tags/' . $releaseVersion]);
        if ($tagExists === '') {
            $releaseVersion = '';
        }
    }

    if ($releaseVersion === '') {
        $releaseVersion = runGitCommand(['describe', '--tags', '--abbrev=0', '--match', 'v*']);
    }

    if ($releaseVersion === '') {
        return [
            'branch' => $branch,
        ];
    }

    $commitsSinceRelease = (int)(runGitCommand(['rev-list', '--count', $releaseVersion . '..HEAD']) ?: '0');
    $diffFilesRaw = runGitCommand(['diff', '--name-only', $releaseVersion . '..HEAD']);
    $changedFilesSinceRelease = $diffFilesRaw === ''
        ? 0
        : count(array_filter(array_map('trim', explode("\n", $diffFilesRaw)), static fn($line) => $line !== ''));

    $displayVersion = $releaseVersion;
    if ($commitsSinceRelease > 0 || $changedFilesSinceRelease > 0) {
        $displayVersion = sprintf(
            '%s+%dc+%df',
            $releaseVersion,
            $commitsSinceRelease,
            $changedFilesSinceRelease
        );
    }

    return [
        'branch' => $branch,
        'releaseVersion' => $releaseVersion,
        'displayVersion' => $displayVersion,
        'commitsSinceRelease' => $commitsSinceRelease,
        'changedFilesSinceRelease' => $changedFilesSinceRelease,
    ];
}

function loadAppMeta(): array
{
    $baseVersion = loadAppVersion();
    $buildMeta = loadBuildMeta();
    $snapshot = loadLatestSnapshot();
    $snapshotGeneratedAt = is_array($snapshot) ? ($snapshot['generated_at'] ?? null) : null;

    $releaseVersion = trim((string)($buildMeta['releaseVersion'] ?? $baseVersion));
    if ($releaseVersion === '') {
        $releaseVersion = $baseVersion;
    }

    $gitMeta = loadGitVersionMeta($releaseVersion);
    if (!empty($gitMeta['releaseVersion'])) {
        $releaseVersion = trim((string)$gitMeta['releaseVersion']);
    }

    $displayVersion = trim((string)($gitMeta['displayVersion'] ?? $buildMeta['displayVersion'] ?? $baseVersion));
    if ($displayVersion === '') {
        $displayVersion = $baseVersion;
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
        'branch' => trim((string)($gitMeta['branch'] ?? $buildMeta['branch'] ?? '')),
        'commitsSinceRelease' => (int)($gitMeta['commitsSinceRelease'] ?? $buildMeta['commitsSinceRelease'] ?? 0),
        'changedFilesSinceRelease' => (int)($gitMeta['changedFilesSinceRelease'] ?? $buildMeta['changedFilesSinceRelease'] ?? 0),
    ];
}

function extractPostalCode(?string $location): string
{
    $location = normalizeText($location);
    if ($location === '') {
        return '';
    }
    if (preg_match('/\b(\d{5})\b/', $location, $m)) {
        return $m[1];
    }
    return '';
}

function loadStatsPassword(): string
{
    $envPassword = trim((string)getenv('PLATZBELEGUNG_STATS_PASSWORD'));
    if ($envPassword !== '') {
        return $envPassword;
    }
    if (!is_file(STATS_PASSWORD_FILE)) {
        return '';
    }
    $raw = trim((string)file_get_contents(STATS_PASSWORD_FILE));
    return $raw;
}

function ensureStatsPasswordAuthorized(string $providedPassword): ?array
{
    $expectedPassword = loadStatsPassword();
    if ($expectedPassword === '') {
        return ['error' => 'Stats-Passwort ist nicht konfiguriert.', 'status' => 503];
    }
    if (!hash_equals($expectedPassword, $providedPassword)) {
        return ['error' => 'Unauthorized', 'status' => 401];
    }
    return null;
}

function loadUsageStats(): array
{
    if (!is_file(USAGE_STATS_FILE)) {
        return ['updatedAt' => null, 'clubs' => []];
    }
    $raw = file_get_contents(USAGE_STATS_FILE);
    if ($raw === false) {
        return ['updatedAt' => null, 'clubs' => []];
    }
    $parsed = json_decode($raw, true);
    if (!is_array($parsed)) {
        return ['updatedAt' => null, 'clubs' => []];
    }
    $clubs = $parsed['clubs'] ?? [];
    if (!is_array($clubs)) {
        $clubs = [];
    }
    return ['updatedAt' => $parsed['updatedAt'] ?? null, 'clubs' => $clubs];
}

function saveUsageStats(array $stats): bool
{
    if (!is_dir(DATA_DIR) && !mkdir(DATA_DIR, 0775, true) && !is_dir(DATA_DIR)) {
        return false;
    }
    $json = json_encode($stats, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) {
        return false;
    }
    return file_put_contents(USAGE_STATS_FILE, $json . PHP_EOL, LOCK_EX) !== false;
}

function sanitizeSharedConfigId(string $value): string
{
    $value = strtoupper(trim($value));
    $value = preg_replace('/[^A-Z0-9]/', '', $value) ?? '';
    return substr($value, 0, 12);
}

function generateSharedConfigId(array $existing): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    for ($attempt = 0; $attempt < 20; $attempt += 1) {
        $id = '';
        for ($i = 0; $i < 6; $i += 1) {
            $id .= $chars[random_int(0, strlen($chars) - 1)];
        }
        if (!isset($existing[$id])) {
            return $id;
        }
    }
    return strtoupper(substr(bin2hex(random_bytes(4)), 0, 8));
}

function loadSharedConfigsStore(): array
{
    if (!is_file(SHARED_CONFIGS_FILE)) {
        return ['updatedAt' => null, 'configs' => []];
    }
    $raw = file_get_contents(SHARED_CONFIGS_FILE);
    if ($raw === false) {
        return ['updatedAt' => null, 'configs' => []];
    }
    $parsed = json_decode($raw, true);
    if (!is_array($parsed)) {
        return ['updatedAt' => null, 'configs' => []];
    }
    $configs = is_array($parsed['configs'] ?? null) ? $parsed['configs'] : [];
    return ['updatedAt' => $parsed['updatedAt'] ?? null, 'configs' => $configs];
}

function saveSharedConfigsStore(array $store): bool
{
    if (!is_dir(DATA_DIR) && !mkdir(DATA_DIR, 0775, true) && !is_dir(DATA_DIR)) {
        return false;
    }
    $store['updatedAt'] = gmdate(DATE_ATOM);
    $json = json_encode($store, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) {
        return false;
    }
    return file_put_contents(SHARED_CONFIGS_FILE, $json . PHP_EOL, LOCK_EX) !== false;
}

function normalizeSharedConfigPayload(array $payload): array
{
    $club = is_array($payload['club'] ?? null) ? $payload['club'] : [];
    $clubId = trim((string)($club['id'] ?? ''));
    $outClub = ['id' => $clubId];
    $clubName = normalizeText((string)($club['name'] ?? ''));
    if ($clubName !== '') {
        $outClub['name'] = $clubName;
    }
    $clubLogoUrl = trim((string)($club['logoUrl'] ?? $club['logo'] ?? ''));
    if ($clubLogoUrl === '' && $clubId !== '') {
        $clubLogoUrl = '/export.media/-/action/getLogo/format/7/id/' . rawurlencode($clubId);
    }
    if ($clubLogoUrl !== '') {
        $outClub['logoUrl'] = toAbsoluteUrl($clubLogoUrl);
    }
    $clubLocation = normalizeText((string)($club['location'] ?? ''));
    if ($clubLocation !== '') {
        $outClub['location'] = $clubLocation;
    }

    $additionalClubs = [];
    foreach (($payload['additionalClubs'] ?? []) as $item) {
        if (!is_array($item)) continue;
        $id = trim((string)($item['id'] ?? ''));
        if ($id === '') continue;
        $entry = ['id' => $id];
        $name = normalizeText((string)($item['name'] ?? ''));
        if ($name !== '') $entry['name'] = $name;
        $logoUrl = trim((string)($item['logoUrl'] ?? $item['logo'] ?? ''));
        if ($logoUrl === '' && $id !== '') {
            $logoUrl = '/export.media/-/action/getLogo/format/7/id/' . rawurlencode($id);
        }
        if ($logoUrl !== '') $entry['logoUrl'] = toAbsoluteUrl($logoUrl);
        $location = normalizeText((string)($item['location'] ?? ''));
        if ($location !== '') $entry['location'] = $location;
        $additionalClubs[] = $entry;
    }

    return [
        'club' => $outClub,
        'additionalClubs' => $additionalClubs,
    ];
}

function listSharedConfigsForAdmin(): array
{
    $store = loadSharedConfigsStore();
    $rows = [];
    foreach (($store['configs'] ?? []) as $id => $config) {
        if (!is_array($config)) continue;
        $rows[] = [
            'id' => sanitizeSharedConfigId((string)$id),
            'club' => is_array($config['club'] ?? null) ? $config['club'] : (object)[],
            'additionalClubs' => is_array($config['additionalClubs'] ?? null) ? array_values($config['additionalClubs']) : [],
            'updatedAt' => $config['updatedAt'] ?? null,
            'createdAt' => $config['createdAt'] ?? null,
            'hits' => (int)($config['hits'] ?? 0),
            'lastAccessedAt' => $config['lastAccessedAt'] ?? null,
        ];
    }
    usort($rows, static function (array $a, array $b): int {
        return strcmp((string)($b['updatedAt'] ?? ''), (string)($a['updatedAt'] ?? ''));
    });
    return $rows;
}

function recordClubParse(string $clubId, string $clubName = '', string $clubLogoUrl = '', string $clubLocation = ''): void
{
    $clubId = trim($clubId);
    if ($clubId === '') {
        return;
    }

    $stats = loadUsageStats();
    $clubs = $stats['clubs'] ?? [];
    $entry = is_array($clubs[$clubId] ?? null) ? $clubs[$clubId] : [];

    $existingLocation = normalizeText((string)($entry['location'] ?? ''));
    $resolvedLocation = normalizeText($clubLocation);
    if ($resolvedLocation === '' && $existingLocation !== '') {
        $resolvedLocation = $existingLocation;
    }

    $entry['id'] = $clubId;
    $entry['name'] = $clubName !== '' ? $clubName : (string)($entry['name'] ?? '');
    $entry['logoUrl'] = $clubLogoUrl !== '' ? $clubLogoUrl : (string)($entry['logoUrl'] ?? '');
    $entry['location'] = $resolvedLocation;
    $entry['postalCode'] = extractPostalCode($resolvedLocation);
    $entry['parses'] = ((int)($entry['parses'] ?? 0)) + 1;
    $entry['lastParsedAt'] = gmdate(DATE_ATOM);

    $clubs[$clubId] = $entry;
    $stats['clubs'] = $clubs;
    $stats['updatedAt'] = gmdate(DATE_ATOM);
    saveUsageStats($stats);
}

function loadTrainingAdminStats(): array
{
    $pendingDir = DATA_DIR . '/requests/pending';
    $pendingRequests = 0;
    if (is_dir($pendingDir)) {
        $files = glob($pendingDir . '/*.json');
        $pendingRequests = is_array($files) ? count($files) : 0;
    }

    $snapshot = loadLatestSnapshot();
    $parsedSessions = 0;
    if (is_array($snapshot)) {
        $sessions = $snapshot['training_sessions'] ?? [];
        if (is_array($sessions)) {
            $parsedSessions = count($sessions);
        }
    }

    return [
        'pendingRequests' => $pendingRequests,
        'parsedSessions' => $parsedSessions,
    ];
}

function loadTrainingCountsByClub(): array
{
    $counts = [];
    $add = function(string $clubName, string $field) use (&$counts): void {
        $name = normalizeText($clubName);
        if ($name === '') return;
        if (!isset($counts[$name])) {
            $counts[$name] = ['requested' => 0, 'parsed' => 0];
        }
        $counts[$name][$field] = (int)($counts[$name][$field] ?? 0) + 1;
    };

    $pendingDir = DATA_DIR . '/requests/pending';
    if (is_dir($pendingDir)) {
        $files = glob($pendingDir . '/*.json');
        if (is_array($files)) {
            foreach ($files as $file) {
                $raw = file_get_contents($file);
                if ($raw === false) continue;
                $entry = json_decode($raw, true);
                if (!is_array($entry)) continue;
                $add((string)($entry['club_name'] ?? ''), 'requested');
            }
        }
    }

    $snapshot = loadLatestSnapshot();
    if (is_array($snapshot)) {
        $sessions = $snapshot['training_sessions'] ?? [];
        if (is_array($sessions)) {
            foreach ($sessions as $session) {
                if (!is_array($session)) continue;
                $clubName = (string)($session['club_name'] ?? $session['clubName'] ?? '');
                $add($clubName, 'parsed');
            }
        }
    }

    return $counts;
}

function buildStatsResponse(array $stats): array
{
    $trainingByClub = loadTrainingCountsByClub();
    $clubs = [];
    foreach (($stats['clubs'] ?? []) as $club) {
        if (!is_array($club)) {
            continue;
        }
        $clubName = normalizeText((string)($club['name'] ?? ''));
        $trainingCounts = $trainingByClub[$clubName] ?? ['requested' => 0, 'parsed' => 0];
        $clubs[] = [
            'id' => (string)($club['id'] ?? ''),
            'name' => (string)($club['name'] ?? ''),
            'logoUrl' => (string)($club['logoUrl'] ?? ''),
            'postalCode' => (string)($club['postalCode'] ?? ''),
            'location' => (string)($club['location'] ?? ''),
            'parses' => (int)($club['parses'] ?? 0),
            'trainingRequested' => (int)($trainingCounts['requested'] ?? 0),
            'trainingParsed' => (int)($trainingCounts['parsed'] ?? 0),
            'lastParsedAt' => $club['lastParsedAt'] ?? null,
        ];
    }
    usort($clubs, function(array $a, array $b): int {
        $cmp = ($b['parses'] ?? 0) <=> ($a['parses'] ?? 0);
        if ($cmp !== 0) {
            return $cmp;
        }
        return strcmp((string)($a['name'] ?? ''), (string)($b['name'] ?? ''));
    });

    $totalParses = 0;
    foreach ($clubs as $club) {
        $totalParses += (int)($club['parses'] ?? 0);
    }

    return [
        'updatedAt' => $stats['updatedAt'] ?? null,
        'totalClubs' => count($clubs),
        'totalParses' => $totalParses,
        'clubs' => $clubs,
        'training' => loadTrainingAdminStats(),
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
        $detail = $gameUrl !== '' ? parseGameDetail($gameUrl) : [];
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

function getJsonBody(): array
{
    $raw = file_get_contents('php://input');
    if (!$raw) return [];
    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

// HTTP-Routing nur im Web-Context ausführen; CLI-Skripte (z.B. parse_matchplan.php)
// können backend.php sicher per require einbinden, ohne dass Routing ausgelöst wird.
// Dazu muss die einbindende Datei PLATZBELEGUNG_CLI_PARSE vor dem require definieren.
if (defined('PLATZBELEGUNG_CLI_PARSE')) {
    return;
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$requestUri = (string)($_SERVER['REQUEST_URI'] ?? '/');
$uri = parse_url($requestUri, PHP_URL_PATH) ?: '/';
parse_str(parse_url($requestUri, PHP_URL_QUERY) ?: '', $query);

// Public POST endpoint for submitting requests must be handled regardless of GET/HEAD block.
if ($method === 'POST' && $uri === '/api/requests/submit') {
    // Öffentlicher Endpoint: nur Anfragen speichern. Keine automatische Verarbeitung.

    // Feldlängen begrenzen, um Disk-Fill-Angriffe zu verhindern
    $maxUrlLen  = 2048;
    $maxTextLen = 4096;
    $maxNameLen = 200;

    $body = getJsonBody();
    $source    = substr(trim((string)($body['source_url'] ?? '')), 0, $maxUrlLen);
    $text      = substr(trim((string)($body['text'] ?? '')), 0, $maxTextLen);
    $club      = substr(trim((string)($body['club_name'] ?? '')), 0, $maxNameLen);
    $team      = substr(trim((string)($body['team'] ?? '')), 0, $maxNameLen);
    $ageClass  = substr(trim((string)($body['age_class'] ?? '')), 0, $maxNameLen);
    $competition = substr(trim((string)($body['competition'] ?? '')), 0, $maxNameLen);
    $submitter = trim((string)($body['submitter'] ?? '')) ?: ($_SERVER['REMOTE_ADDR'] ?? 'web');

    if ($source === '' && $text === '') { jsonResponse(['error' => 'source_url or text required'], 400); return; }

    // Einfaches IP-basiertes Rate-Limiting: max. 5 Anfragen pro IP pro 10 Minuten
    $clientIp = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $rateDir  = DATA_DIR . '/requests/ratelimit';
    if (!is_dir($rateDir) && !mkdir($rateDir, 0775, true) && !is_dir($rateDir)) {
        jsonResponse(['error' => 'Could not create ratelimit directory'], 500); return;
    }
    $rateFile = $rateDir . '/' . md5($clientIp) . '.json';
    $rateWindow = 600; // 10 Minuten in Sekunden
    $rateLimit  = 5;
    $now = time();
    $rateData = [];
    if (file_exists($rateFile)) {
        $rateData = json_decode((string)file_get_contents($rateFile), true) ?: [];
    }
    // Einträge außerhalb des Fensters entfernen
    $rateData = array_values(array_filter($rateData, fn($ts) => ($now - $ts) < $rateWindow));
    if (count($rateData) >= $rateLimit) {
        jsonResponse(['error' => 'Zu viele Anfragen. Bitte später erneut versuchen.'], 429); return;
    }
    $rateData[] = $now;
    file_put_contents($rateFile, json_encode($rateData), LOCK_EX);

    if ($source !== '') {
        if (!preg_match('/^https?:\/\//i', $source)) {
            if (str_starts_with($source, '/')) {
                $source = toAbsoluteUrl($source);
            } else {
                jsonResponse(['error' => 'Invalid source_url'], 400); return;
            }
        }
    }

    $id = 'req-' . gmdate('Ymd\THis') . '-' . substr(md5($source . $text . $submitter), 0, 6);
    $dir = DATA_DIR . '/requests/pending';
    if (!is_dir($dir) && !mkdir($dir, 0775, true) && !is_dir($dir)) {
        jsonResponse(['error' => 'Could not create requests directory'], 500); return;
    }

    $payload = [
        'id' => $id,
        'submitted_at' => gmdate(DATE_ATOM),
        'submitter' => $submitter,
        'body' => [
            'source_url'  => $source,
            'text'        => $text,
            'club_name'   => $club,
            'team'        => $team,
            'age_class'   => $ageClass,
            'competition' => $competition,
        ],
    ];

    $fn = $dir . '/' . $id . '.json';
    $json = json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    if ($json === false) { jsonResponse(['error' => 'Encoding error'], 500); return; }
    if (file_put_contents($fn, $json . PHP_EOL, LOCK_EX) === false) { jsonResponse(['error' => 'Could not save request'], 500); return; }

    jsonResponse(['ok' => true, 'id' => $id, 'path' => str_replace(__DIR__ . '/', '', $fn)]);
    return;
}

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
        $clubName = trim((string)($query['clubName'] ?? ''));
        $clubLogoUrl = trim((string)($query['clubLogoUrl'] ?? ''));
        $clubLocation = trim((string)($query['clubLocation'] ?? ''));
        if ($id === '') { jsonResponse(['error' => 'Vereins-ID erforderlich.'], 400); return; }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateFrom)) { jsonResponse(['error' => 'dateFrom muss im Format YYYY-MM-DD angegeben werden.'], 400); return; }
        if (!preg_match('/^\d{4}-\d{2}-\d{2}$/', $dateTo)) { jsonResponse(['error' => 'dateTo muss im Format YYYY-MM-DD angegeben werden.'], 400); return; }
        $max = min(max($max, 1), 200);
        $url = FUSSBALL_DE_BASE . '/ajax.club.matchplan/-/id/' . rawurlencode($id) . '/mode/PAGE/show-filter/false/max/' . rawurlencode((string)$max) . '/datum-von/' . rawurlencode($dateFrom) . '/datum-bis/' . rawurlencode($dateTo) . '/match-type/' . rawurlencode((string)$matchType) . '/show-venues/checked/offset/0';
        try {
            $games = parseClubMatchplanHtml(httpGet($url));
            recordClubParse($id, $clubName, $clubLogoUrl, $clubLocation);
            jsonResponse($games);
        } catch (Throwable $e) {
            jsonResponse(['error' => 'Fehler beim Laden des Vereinsspielplans'], 502);
        }
        return;
    }

    if ($uri === '/api/admin/club-parse-stats') {
        $providedPassword = (string)($query['password'] ?? '');
        $authError = ensureStatsPasswordAuthorized($providedPassword);
        if ($authError !== null) {
            jsonResponse(['error' => $authError['error']], (int)$authError['status']);
            return;
        }
        jsonResponse(buildStatsResponse(loadUsageStats()));
        return;
    }

    if ($uri === '/api/admin/config') {
        $providedPassword = (string)($query['password'] ?? '');
        $authError = ensureStatsPasswordAuthorized($providedPassword);
        if ($authError !== null) {
            jsonResponse(['error' => $authError['error']], (int)$authError['status']);
            return;
        }
        $config = loadConfig();
        if ($config === null) {
            jsonResponse(['error' => 'config.yaml nicht gefunden.'], 404);
            return;
        }
        jsonResponse($config);
        return;
    }

    if ($uri === '/api/admin/dashboard') {
        $providedPassword = (string)($query['password'] ?? '');
        $authError = ensureStatsPasswordAuthorized($providedPassword);
        if ($authError !== null) {
            jsonResponse(['error' => $authError['error']], (int)$authError['status']);
            return;
        }
        $config = loadConfig();
        jsonResponse([
            'stats' => buildStatsResponse(loadUsageStats()),
            'config' => $config === null ? null : $config,
            'configAvailable' => $config !== null,
            'sharedConfigs' => listSharedConfigsForAdmin(),
        ]);
        return;
    }

    if ($uri === '/api/admin/shared-configs') {
        $providedPassword = (string)($query['password'] ?? '');
        $authError = ensureStatsPasswordAuthorized($providedPassword);
        if ($authError !== null) {
            jsonResponse(['error' => $authError['error']], (int)$authError['status']);
            return;
        }
        jsonResponse(['configs' => listSharedConfigsForAdmin()]);
        return;
    }

    if ($uri === '/api/shared-config') {
        $id = sanitizeSharedConfigId((string)($query['id'] ?? ''));
        if ($id === '') {
            jsonResponse(['error' => 'Konfigurations-ID erforderlich.'], 400);
            return;
        }
        $store = loadSharedConfigsStore();
        $config = $store['configs'][$id] ?? null;
        if (!is_array($config)) {
            jsonResponse(['error' => 'Konfiguration nicht gefunden.'], 404);
            return;
        }
        $config['hits'] = ((int)($config['hits'] ?? 0)) + 1;
        $config['lastAccessedAt'] = gmdate(DATE_ATOM);
        $store['configs'][$id] = $config;
        saveSharedConfigsStore($store);
        jsonResponse([
            'id' => $id,
            'club' => is_array($config['club'] ?? null) ? $config['club'] : (object)[],
            'additionalClubs' => is_array($config['additionalClubs'] ?? null) ? array_values($config['additionalClubs']) : [],
            'updatedAt' => $config['updatedAt'] ?? null,
        ]);
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

if ($method === 'POST' && $uri === '/api/shared-config') {
    $body = getJsonBody();
    $payload = normalizeSharedConfigPayload($body);
    $clubId = trim((string)($payload['club']['id'] ?? ''));
    if ($clubId === '') {
        jsonResponse(['error' => 'Mindestens ein Verein ist erforderlich.'], 400);
        return;
    }
    $store = loadSharedConfigsStore();
    $configs = is_array($store['configs'] ?? null) ? $store['configs'] : [];
    $id = sanitizeSharedConfigId((string)($body['id'] ?? ''));
    if ($id === '') {
        $id = generateSharedConfigId($configs);
    }
    $now = gmdate(DATE_ATOM);
    $existing = is_array($configs[$id] ?? null) ? $configs[$id] : [];
    $configs[$id] = [
        'club' => $payload['club'],
        'additionalClubs' => $payload['additionalClubs'],
        'createdAt' => $existing['createdAt'] ?? $now,
        'updatedAt' => $now,
        'hits' => (int)($existing['hits'] ?? 0),
        'lastAccessedAt' => $existing['lastAccessedAt'] ?? null,
    ];
    $store['configs'] = $configs;
    if (!saveSharedConfigsStore($store)) {
        jsonResponse(['error' => 'Konfiguration konnte nicht gespeichert werden.'], 500);
        return;
    }
    jsonResponse(['ok' => true, 'id' => $id, 'config' => $configs[$id]]);
    return;
}

if ($method === 'PATCH' && $uri === '/api/admin/shared-config') {
    $providedPassword = (string)($_GET['password'] ?? '');
    $authError = ensureStatsPasswordAuthorized($providedPassword);
    if ($authError !== null) {
        jsonResponse(['error' => $authError['error']], (int)$authError['status']);
        return;
    }
    $id = sanitizeSharedConfigId((string)($_GET['id'] ?? ''));
    if ($id === '') {
        jsonResponse(['error' => 'Konfigurations-ID erforderlich.'], 400);
        return;
    }
    $body = getJsonBody();
    $newId = sanitizeSharedConfigId((string)($body['newId'] ?? ''));
    if ($newId === '') {
        jsonResponse(['error' => 'Neue Konfigurations-ID erforderlich.'], 400);
        return;
    }
    $store = loadSharedConfigsStore();
    $config = $store['configs'][$id] ?? null;
    if (!is_array($config)) {
        jsonResponse(['error' => 'Konfiguration nicht gefunden.'], 404);
        return;
    }
    if ($newId !== $id && isset($store['configs'][$newId])) {
        jsonResponse(['error' => 'Konfigurations-ID bereits vorhanden.'], 409);
        return;
    }
    $config['updatedAt'] = gmdate(DATE_ATOM);
    unset($store['configs'][$id]);
    $store['configs'][$newId] = $config;
    if (!saveSharedConfigsStore($store)) {
        jsonResponse(['error' => 'Konfiguration konnte nicht umbenannt werden.'], 500);
        return;
    }
    jsonResponse(['ok' => true, 'id' => $newId]);
    return;
}

if ($method === 'DELETE' && $uri === '/api/admin/shared-config') {
    $providedPassword = (string)($_GET['password'] ?? '');
    $authError = ensureStatsPasswordAuthorized($providedPassword);
    if ($authError !== null) {
        jsonResponse(['error' => $authError['error']], (int)$authError['status']);
        return;
    }
    $id = sanitizeSharedConfigId((string)($_GET['id'] ?? ''));
    if ($id === '') {
        jsonResponse(['error' => 'Konfigurations-ID erforderlich.'], 400);
        return;
    }
    $store = loadSharedConfigsStore();
    if (!isset($store['configs'][$id])) {
        jsonResponse(['error' => 'Konfiguration nicht gefunden.'], 404);
        return;
    }
    unset($store['configs'][$id]);
    if (!saveSharedConfigsStore($store)) {
        jsonResponse(['error' => 'Konfiguration konnte nicht gelöscht werden.'], 500);
        return;
    }
    jsonResponse(['ok' => true]);
    return;
}

if (($method === 'GET' || $method === 'HEAD') && ($uri === '/' || !str_starts_with($uri, '/api/'))) {
    $file = $uri === '/' ? '/index.html' : $uri;
    if ($uri === '/admin') {
        $file = '/admin.html';
    }
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
