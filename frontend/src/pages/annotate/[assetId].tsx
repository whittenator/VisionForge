import React from 'react';
import Annotator from '@/pages/annotate/Annotator';
import Button from '@/components/ui/Button';

export default function AnnotateAsset() {
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Annotator</h2>
          <p className="text-sm text-gray-600">Keyboard-first: b = box, c = cat, Enter = save, arrows = navigate</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline">Previous</Button>
          <Button>Save</Button>
          <Button variant="outline">Next</Button>
        </div>
      </div>
      <Annotator />
    </div>
  );
}
