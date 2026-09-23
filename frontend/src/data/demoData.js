export const demoCases = [
  { id: 'CASE-1042', result: 'positive', confidence: 0.91, officer: 'Ram Gupta', time: '22:08', location: 'Sector 67 · Mohali', integrity: 'verified', image: '/demo-images/positive_style.jpg' },
  { id: 'CASE-1041', result: 'negative', confidence: 0.88, officer: 'Amay Verma', time: '21:52', location: 'Phase 8 · Mohali', integrity: 'verified', image: '/demo-images/negative_style.jpg' },
  { id: 'CASE-1040', result: 'invalid', confidence: 0.63, officer: 'Ram Gupta', time: '21:31', location: 'Kharar · Punjab', integrity: 'review', image: '/demo-images/blurred.jpg' },
  { id: 'CASE-1039', result: 'positive', confidence: 0.89, officer: 'Neeraj Singh', time: '20:47', location: 'Zirakpur · Punjab', integrity: 'verified', image: '/demo-images/positive_style.jpg' },
  { id: 'CASE-1038', result: 'negative', confidence: 0.93, officer: 'Amay Verma', time: '20:15', location: 'Phase 3B2 · Mohali', integrity: 'verified', image: '/demo-images/negative_style.jpg' },
]

export const trendData = [
  { day: '18', p: 5, n: 18, i: 2 },
  { day: '19', p: 7, n: 21, i: 3 },
  { day: '20', p: 4, n: 15, i: 2 },
  { day: '21', p: 8, n: 22, i: 4 },
  { day: '22', p: 6, n: 19, i: 3 },
  { day: '23', p: 9, n: 25, i: 2 },
  { day: '24', p: 7, n: 24, i: 4 },
]

export const pipelineLabels = [
  ['01', 'Image quality'],
  ['02', 'Reference calibration'],
  ['03', 'Strip ROI'],
  ['04', 'Rule engine'],
  ['05', 'ML corroboration'],
  ['06', 'Evidence seal'],
]
