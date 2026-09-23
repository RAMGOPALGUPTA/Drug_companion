import React, {useEffect, useRef, useState} from 'react';
import {Alert, Pressable, StyleSheet, Text, View} from 'react-native';
import {CameraView, useCameraPermissions} from 'expo-camera';
import LocationService from '../services/LocationService';
import StorageService from '../services/StorageService';
import CameraService from '../services/CameraService';
import ApiService from '../services/ApiService';
import {useAuth} from '../store/authContext';

export default function TestCaptureScreen({navigation}) {
  const camera = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [busy, setBusy] = useState(false);
  const [location, setLocation] = useState(null);
  const {officer} = useAuth();

  useEffect(() => {
    requestPermission();
    LocationService.getCurrentLocation().then(setLocation).catch(() => setLocation(null));
  }, [requestPermission]);

  if (!permission) return <View style={s.loading}><Text style={s.muted}>Preparing camera…</Text></View>;
  if (!permission.granted) return <View style={s.loading}>
    <Text style={s.title}>Camera access required</Text>
    <Pressable style={s.button} onPress={requestPermission}><Text style={s.buttonText}>Allow camera</Text></Pressable>
  </View>;

  const capture = async () => {
    if (busy || !camera.current) return;
    setBusy(true);
    try {
      const photo = await camera.current.takePictureAsync({quality: 0.85});
      const imagePath = await StorageService.saveImage(photo.uri);
      const imageHash = await CameraService.hash(imagePath);
      const record = {
        officer_id: officer.officer_id,
        test_type: 'colorimetric_field_test',
        // A real result is unavailable until the labelled model is validated.
        result: 'inconclusive',
        confidence_score: 0,
        image_path: imagePath,
        image_hash: imageHash,
        latitude: location?.latitude || null,
        longitude: location?.longitude || null,
        accuracy: location?.accuracy || null,
        device_info: 'expo-mobile',
        digital_signature: '',
      };
      const id = await StorageService.addTestRecord(record);
      const sync = await ApiService.syncPending();
      navigation.navigate('Result', {record: {...record, id, sync}});
    } catch (error) {
      Alert.alert('Capture failed', 'Please retry the test capture.');
    } finally {
      setBusy(false);
    }
  };

  return <View style={s.page}>
    <CameraView ref={camera} style={s.camera} facing="back">
      <View style={s.overlay}>
        <View style={s.guide}>
          <View style={s.corner}/>
          <Text style={s.guideText}>Place test strip + reference card here</Text>
        </View>
        <View style={s.bottom}>
          <Text style={s.hint}>{location ? 'GPS ready' : 'GPS unavailable or loading'}</Text>
          <Pressable style={s.shutter} onPress={capture} disabled={busy}><View style={s.inner}/></Pressable>
          <Text style={s.hint}>{busy ? 'Saving and synchronizing…' : 'Tap to capture'}</Text>
        </View>
      </View>
    </CameraView>
  </View>;
}

const s = StyleSheet.create({
  page: {flex: 1, backgroundColor: '#000'}, camera: {flex: 1},
  overlay: {flex: 1, backgroundColor: 'rgba(0,0,0,.25)', justifyContent: 'space-between', paddingTop: 70, paddingBottom: 35},
  guide: {alignSelf: 'center', width: '82%', height: 310, borderWidth: 2, borderColor: '#fff', borderRadius: 22, justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 18},
  corner: {position: 'absolute', top: -2, left: -2, height: 60, width: 60, borderTopWidth: 5, borderLeftWidth: 5, borderColor: '#ff6b35', borderTopLeftRadius: 20},
  guideText: {color: '#fff', fontWeight: '700', backgroundColor: 'rgba(0,0,0,.55)', padding: 9, borderRadius: 10},
  bottom: {alignItems: 'center'}, hint: {color: '#fff', fontSize: 12, marginBottom: 10},
  shutter: {width: 78, height: 78, borderRadius: 39, borderWidth: 5, borderColor: '#fff', alignItems: 'center', justifyContent: 'center'},
  inner: {width: 62, height: 62, borderRadius: 31, backgroundColor: '#ff6b35'},
  loading: {flex: 1, backgroundColor: '#07111f', alignItems: 'center', justifyContent: 'center', padding: 25},
  title: {color: '#fff', fontSize: 22, fontWeight: '800', marginBottom: 20}, muted: {color: '#94a3b8'},
  button: {backgroundColor: '#ff6b35', padding: 15, borderRadius: 12}, buttonText: {color: '#fff', fontWeight: '800'},
});
