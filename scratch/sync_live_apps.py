import os
import glob

animated_jsx = '''import React, { useState, useEffect } from 'react';

export const AnimatedHelloWorld = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [message, setMessage] = useState('Hello World');
  const [animationStep, setAnimationStep] = useState(0);

  const greetings = ['Hello World', '👋 Hello World', '✨ Hello World ✨', '🚀 Hello World 🚀'];

  useEffect(() => {
    let interval = null;
    if (isVisible) {
      interval = setInterval(() => {
        setAnimationStep((prevStep) => {
          const nextStep = (prevStep + 1) % greetings.length;
          setMessage(greetings[nextStep]);
          return nextStep;
        });
      }, 1000);
    } else {
      if (interval) clearInterval(interval);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [isVisible]);

  const handleShow = () => {
    setIsVisible(true);
    setAnimationStep(0);
    setMessage(greetings[0]);
  };

  const handleHide = () => {
    setIsVisible(false);
  };

  if (!isVisible) {
    return (
      <div style={{ margin: '24px auto', textAlign: 'center' }}>
        <button
          type="button"
          onClick={handleShow}
          style={{
            padding: '14px 32px',
            fontSize: '16px',
            fontWeight: 'bold',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #0284c7 0%, #6366f1 100%)',
            color: '#ffffff',
            border: 'none',
            cursor: 'pointer',
            boxShadow: '0 4px 18px rgba(2, 132, 199, 0.45)',
            transition: 'all 0.2s ease',
          }}
        >
          🚀 Launch Animated Hello World
        </button>
      </div>
    );
  }

  const containerStyle = {
    position: 'fixed',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    fontSize: '2.5rem',
    fontWeight: 'bold',
    color: '#38bdf8',
    padding: '36px 52px',
    backgroundColor: '#0f172a',
    border: '2px solid #38bdf8',
    borderRadius: '16px',
    boxShadow: '0 20px 50px rgba(0, 0, 0, 0.85), 0 0 30px rgba(56, 189, 248, 0.35)',
    textAlign: 'center',
    zIndex: 9999,
  };

  return (
    <div style={containerStyle}>
      <div style={{ marginBottom: '16px', minWidth: '320px' }}>{message}</div>
      <div>
        <button
          type="button"
          onClick={handleHide}
          style={{
            padding: '8px 24px',
            fontSize: '13px',
            fontWeight: 600,
            borderRadius: '8px',
            background: '#334155',
            color: '#f8fafc',
            border: '1px solid #475569',
            cursor: 'pointer',
          }}
        >
          Close Animation
        </button>
      </div>
    </div>
  );
};

export default AnimatedHelloWorld;
'''

base = os.path.expandvars('%TEMP%')
all_apps = glob.glob(base + '/**/src/App.jsx', recursive=True)
updated = []

for app_path in all_apps:
    try:
        with open(app_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if 'Message is' in content:
            src_dir = os.path.dirname(app_path)
            anim_path = os.path.join(src_dir, 'AnimatedHelloWorld.jsx')
            with open(anim_path, 'w', encoding='utf-8') as f:
                f.write(animated_jsx)

            if 'AnimatedHelloWorld' not in content:
                new_content = "import AnimatedHelloWorld from './AnimatedHelloWorld';\n" + content
                if '</section>' in new_content:
                    new_content = new_content.replace(
                        '</section>',
                        '        <AnimatedHelloWorld />\n      </section>'
                    )
                with open(app_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated.append(app_path + ' (UPDATED)')
            else:
                updated.append(app_path + ' (ALREADY_IMPORTED)')
    except Exception as e:
        pass

print("RESULTS:")
for u in updated:
    print(" -", u)
