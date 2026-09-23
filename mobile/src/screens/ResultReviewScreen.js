import React from 'react';
import {Image, Pressable, ScrollView, StyleSheet, Text, View} from 'react-native';

export default function ResultReviewScreen({route, navigation}) {
  const record = route.params?.record || {};
  const syncLabel = record.sync?.pending
    ? `${record.sync.pending} record(s) remain in the local outbox`
    : 'Synchronized to the operations API';
  return <ScrollView style={s.page} contentContainerStyle={s.content}>
    <Text style={s.kicker}>TEST RESULT</Text><Text style={s.title}>Review observation</Text>
    {record.image_path ? <Image source={{uri: record.image_path}} style={s.image}/> : null}
    <View style={s.result}>
      <Text style={s.resultLabel}>INTERPRETATION</Text><Text style={s.resultValue}>INCONCLUSIVE</Text>
      <Text style={s.resultSub}>No trained model is installed yet. This record remains inconclusive rather than asserting a classification.</Text>
    </View>
    <View style={s.card}>
      <Row k="Confidence" v="0%"/>
      <Row k="GPS" v={record.latitude ? `${record.latitude.toFixed(5)}, ${record.longitude.toFixed(5)}` : 'Unavailable'}/>
      <Row k="Evidence SHA-256" v={record.image_hash || 'Unavailable'}/>
      <Row k="Sync" v={syncLabel}/><Row k="Local record" v={String(record.id || '—')}/>
    </View>
    <Pressable style={s.button} onPress={() => navigation.navigate('Dashboard')}><Text style={s.buttonText}>Done</Text></Pressable>
  </ScrollView>;
}

function Row({k, v}) { return <View style={s.row}><Text style={s.k}>{k}</Text><Text style={s.v} numberOfLines={2}>{v}</Text></View>; }

const s = StyleSheet.create({
  page: {flex: 1, backgroundColor: '#07111f'}, content: {padding: 20, paddingBottom: 40},
  kicker: {color: '#ff8b63', fontWeight: '800', fontSize: 11, letterSpacing: 1.4}, title: {color: '#fff', fontSize: 28, fontWeight: '800', marginTop: 5, marginBottom: 18},
  image: {height: 220, borderRadius: 20, marginBottom: 15}, result: {backgroundColor: '#192333', borderRadius: 20, padding: 20, borderWidth: 1, borderColor: '#334155'},
  resultLabel: {color: '#94a3b8', fontSize: 11, fontWeight: '800', letterSpacing: 1}, resultValue: {color: '#fbbf24', fontSize: 29, fontWeight: '900', marginTop: 5}, resultSub: {color: '#94a3b8', lineHeight: 19, marginTop: 7},
  card: {backgroundColor: '#0d1b2a', borderRadius: 20, padding: 18, marginTop: 15}, row: {paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#1c2b3d'},
  k: {color: '#71839a', fontSize: 12}, v: {color: '#e2e8f0', fontSize: 13, marginTop: 4}, button: {marginTop: 18, backgroundColor: '#ff6b35', padding: 16, borderRadius: 13, alignItems: 'center'}, buttonText: {color: '#fff', fontWeight: '800', fontSize: 16},
});
