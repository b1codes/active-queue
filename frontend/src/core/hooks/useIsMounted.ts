import { useEffect, useRef, type RefObject } from 'react';

/**
 * `.current` is false once the component has unmounted. Check it before navigating after
 * an await: if the user swiped back while the request was in flight, a late
 * router.push/replace would pull them off whatever screen they went to.
 */
export function useIsMounted(): RefObject<boolean> {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}
