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
    expect(screen.getByText(/RORI \/\/ COPILOT AI/i)).toBeInTheDocument();
    expect(screen.getByText(/Sarthak Pandey/i)).toBeInTheDocument();
  });
});
