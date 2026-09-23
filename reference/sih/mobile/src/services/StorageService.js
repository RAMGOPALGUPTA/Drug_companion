import * as SQLite from 'expo-sqlite';
import * as FileSystem from 'expo-file-system';

const appVersion = '1.1.0';
const pendingModelVersion = 'pending-labelled-training-data';

function newCaseId() {
  const bytes = Array.from({length: 16}, () => Math.floor(Math.random() * 256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const value = bytes.map((byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${value.slice(0, 8)}-${value.slice(8, 12)}-${value.slice(12, 16)}-${value.slice(16, 20)}-${value.slice(20)}`;
}

class StorageService {
  db = null;

  async init() {
    if (this.db) return;
    this.db = await SQLite.openDatabaseAsync('FieldDrugTesting.db');
    await this.db.execAsync(`
      CREATE TABLE IF NOT EXISTS officers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, officer_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL, pin TEXT NOT NULL,
        designation TEXT, district TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS test_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT UNIQUE, officer_id TEXT NOT NULL,
        test_type TEXT, result TEXT, confidence_score REAL, image_path TEXT,
        image_hash TEXT, latitude REAL, longitude REAL, accuracy REAL,
        device_info TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP, synced INTEGER DEFAULT 0,
        digital_signature TEXT, captured_at TEXT, model_version TEXT, app_version TEXT
      );
      CREATE TABLE IF NOT EXISTS metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT, test_record_id INTEGER NOT NULL,
        gps_latitude REAL, gps_longitude REAL, accuracy_meters REAL, device_info TEXT,
        app_version TEXT, network_type TEXT
      );
      CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT, test_record_id INTEGER NOT NULL UNIQUE,
        status TEXT DEFAULT 'pending', error_message TEXT, retry_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
    `);
    await this._addMissingColumns();
    const directory = `${FileSystem.documentDirectory}images/`;
    const info = await FileSystem.getInfoAsync(directory);
    if (!info.exists) await FileSystem.makeDirectoryAsync(directory, {intermediates: true});
  }

  async _addMissingColumns() {
    const existing = await this.db.getAllAsync('PRAGMA table_info(test_records)');
    const names = new Set(existing.map((column) => column.name));
    const additions = [
      ['case_id', 'TEXT'], ['captured_at', 'TEXT'],
      ['model_version', 'TEXT'], ['app_version', 'TEXT'],
    ];
    for (const [name, definition] of additions) {
      if (!names.has(name)) await this.db.execAsync(`ALTER TABLE test_records ADD COLUMN ${name} ${definition}`);
    }
    const legacyRecords = await this.db.getAllAsync(
      'SELECT id, case_id, captured_at, timestamp, model_version, app_version FROM test_records',
    );
    for (const record of legacyRecords) {
      const legacyTimestamp = record.timestamp ? `${String(record.timestamp).replace(' ', 'T')}Z` : null;
      const capturedAt = record.captured_at || (legacyTimestamp && !Number.isNaN(Date.parse(legacyTimestamp))
        ? new Date(legacyTimestamp).toISOString() : new Date().toISOString());
      await this.db.runAsync(
        `UPDATE test_records SET case_id=COALESCE(case_id, ?), captured_at=COALESCE(captured_at, ?),
         model_version=COALESCE(model_version, ?), app_version=COALESCE(app_version, ?) WHERE id=?`,
        [newCaseId(), capturedAt, pendingModelVersion, appVersion, record.id],
      );
    }
  }

  async addOfficer(officer) {
    await this.init();
    return (await this.db.runAsync(
      'INSERT OR REPLACE INTO officers(officer_id,name,phone,pin,designation,district) VALUES(?,?,?,?,?,?)',
      [officer.officer_id, officer.name, officer.phone, officer.pin, officer.designation || '', officer.district || ''],
    )).lastInsertRowId;
  }

  async getOfficer(id) {
    await this.init();
    return this.db.getFirstAsync('SELECT * FROM officers WHERE officer_id=?', [id]);
  }

  async addTestRecord(test) {
    await this.init();
    const capturedAt = new Date().toISOString();
    const result = await this.db.runAsync(
      `INSERT INTO test_records(
        case_id, officer_id, test_type, result, confidence_score, image_path,
        image_hash, latitude, longitude, accuracy, device_info, digital_signature,
        captured_at, model_version, app_version
      ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      [
        newCaseId(), test.officer_id, test.test_type, test.result, test.confidence_score,
        test.image_path, test.image_hash, test.latitude, test.longitude, test.accuracy,
        test.device_info, test.digital_signature, capturedAt,
        pendingModelVersion, appVersion,
      ],
    );
    await this.db.runAsync('INSERT OR REPLACE INTO sync_queue(test_record_id,status) VALUES(?,?)', [result.lastInsertRowId, 'pending']);
    return result.lastInsertRowId;
  }

  async getTestRecords(officerId) {
    await this.init();
    return this.db.getAllAsync('SELECT * FROM test_records WHERE officer_id=? ORDER BY timestamp DESC', [officerId]);
  }

  async getStats(officerId) {
    await this.init();
    return this.db.getFirstAsync(
      `SELECT COUNT(*) AS total_tests, SUM(result='positive') AS positive_count,
       SUM(result='negative') AS negative_count, SUM(result='inconclusive') AS inconclusive_count,
       COALESCE(AVG(confidence_score),0) AS avg_confidence FROM test_records WHERE officer_id=?`,
      [officerId],
    );
  }

  async getPendingRecords() {
    await this.init();
    return this.db.getAllAsync(`
      SELECT test_records.* FROM test_records
      JOIN sync_queue ON sync_queue.test_record_id = test_records.id
      WHERE sync_queue.status IN ('pending', 'failed') ORDER BY sync_queue.created_at ASC
    `);
  }

  async markSynced(recordId) {
    await this.init();
    await this.db.runAsync('UPDATE test_records SET synced=1 WHERE id=?', [recordId]);
    await this.db.runAsync("UPDATE sync_queue SET status='synced', error_message=NULL WHERE test_record_id=?", [recordId]);
  }

  async markSyncFailure(recordId, message) {
    await this.init();
    await this.db.runAsync(
      "UPDATE sync_queue SET status='failed', error_message=?, retry_count=retry_count+1 WHERE test_record_id=?",
      [String(message).slice(0, 240), recordId],
    );
  }

  async pendingCount() {
    await this.init();
    const row = await this.db.getFirstAsync("SELECT COUNT(*) AS count FROM sync_queue WHERE status IN ('pending', 'failed')");
    return Number(row?.count || 0);
  }

  async saveImage(uri) {
    await this.init();
    const destination = `${FileSystem.documentDirectory}images/${Date.now()}.jpg`;
    await FileSystem.copyAsync({from: uri, to: destination});
    return destination;
  }
}

export default new StorageService();
