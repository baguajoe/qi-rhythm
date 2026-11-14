import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';

export function useLibrary() {
  const [data, setData] = useState({ genres: [], rhythms: [], loading: true, error: '' });
  useEffect(() => {
    let live = true;
    Promise.all([api('/api/genres'), api('/api/rhythms')])
      .then(
        ([g, r]) =>
          live && setData({ genres: g.genres, rhythms: r.rhythms, loading: false, error: '' }),
      )
      .catch((e) => live && setData((d) => ({ ...d, loading: false, error: e.message })));
    return () => {
      live = false;
    };
  }, []);
  return data;
}

export const DIFFICULTY_LABEL = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
};
