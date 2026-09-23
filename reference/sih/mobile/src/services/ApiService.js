import StorageService from './StorageService';

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://10.0.2.2:8000';
const apiOperatorId = process.env.EXPO_PUBLIC_API_OPERATOR_ID || 'demo-operator';

function payloadFor(record) {
  if (!/^[a-f0-9]{64}$/i.test(record.image_hash || '')) {
    throw new Error('A valid evidence digest is required before sync.');
  }
  return {
    id: record.case_id,
    // The API development database exposes demo-operator. Production must map
    // authenticated field officers to provisioned API operators before sync.
    operator_id: apiOperatorId,
    classification: record.result || 'inconclusive',
    confidence: Number(record.confidence_score || 0),
    latitude: record.latitude,
    longitude: record.longitude,
    captured_at: record.captured_at,
    model_version: record.model_version || 'pending-labelled-training-data',
    app_version: record.app_version || '1.1.0',
    image_sha256: record.image_hash.toLowerCase(),
  };
}

class ApiService {
  async syncPending() {
    const records = await StorageService.getPendingRecords();
    let synced = 0;
    for (const record of records) {
      try {
        const response = await fetch(`${apiBaseUrl}/api/v1/cases`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payloadFor(record)),
        });
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(`Server rejected record (${response.status}): ${detail}`);
        }
        await StorageService.markSynced(record.id);
        synced += 1;
      } catch (error) {
        await StorageService.markSyncFailure(record.id, error.message || 'Network unavailable');
        break;
      }
    }
    return {synced, pending: await StorageService.pendingCount()};
  }
}

export default new ApiService();
