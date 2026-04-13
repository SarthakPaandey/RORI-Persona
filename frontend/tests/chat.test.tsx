import { render, screen } from '@testing-library/react';

import Header from '@/components/Header';

describe('Header', () => {
  it('renders title', () => {
    render(
      <Header
        name="Sarthak Pandey"
        role="AI Engineer"
        resumeConfigured={true}
        voiceEnabled={true}
      />
    );
    expect(screen.getByText(/Sarthak Pandey's AI Representative/i)).toBeInTheDocument();
  });
});
