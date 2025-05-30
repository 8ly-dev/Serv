# Multi-Step Form Wizard Demo (MVP)

A comprehensive form wizard built with Serv showcasing advanced form handling, validation, file uploads, and session management.

## Features

- Multi-step form progression
- Form validation and error handling
- File upload integration
- Session-based state management
- Progress indicator
- Form data persistence

## MVP TODO List

### Form Wizard Core
- [ ] Create multi-step form structure
- [ ] Implement session-based form state storage
- [ ] Add form progression logic (next/previous)
- [ ] Create form validation for each step
- [ ] Handle form completion and summary

### Form Steps
- [ ] Step 1: Personal Information (name, email, phone)
- [ ] Step 2: Address Information (address, city, state, zip)
- [ ] Step 3: File Upload (profile picture, documents)
- [ ] Step 4: Preferences (checkboxes, radio buttons, select)
- [ ] Step 5: Review and Submit (summary of all data)

### Form Validation
- [ ] Client-side validation with JavaScript
- [ ] Server-side validation in Serv
- [ ] Real-time validation feedback
- [ ] Error message display
- [ ] Field highlighting for errors

### User Interface
- [ ] Progress indicator showing current step
- [ ] Navigation buttons (Next, Previous, Submit)
- [ ] Form styling with CSS
- [ ] Responsive design for mobile
- [ ] Loading states and transitions

### Data Handling
- [ ] Session storage for form data
- [ ] File upload handling for step 3
- [ ] Data persistence between steps
- [ ] Form completion handling
- [ ] Data export/display after submission

### Extensions Integration
- [ ] Create FormWizardExtension
- [ ] Add form validation middleware
- [ ] Create session management extension
- [ ] Add file upload handling

## Running the Demo

```bash
cd demos/form_wizard
pip install -r requirements.txt  # Pillow for image handling
serv launch
```

Visit http://localhost:8000 to start the form wizard!

## File Structure

```
demos/form_wizard/
├── README.md
├── requirements.txt              # Pillow for image handling
├── serv.config.yaml             # Basic config
├── uploads/                     # File storage for form uploads
├── extensions/
│   └── form_wizard_extension.py # Form routes and logic
├── templates/
│   ├── wizard_step1.html       # Personal info step
│   ├── wizard_step2.html       # Address step
│   ├── wizard_step3.html       # File upload step
│   ├── wizard_step4.html       # Preferences step
│   ├── wizard_step5.html       # Review and submit
│   └── wizard_complete.html    # Completion page
└── static/
    ├── wizard.js               # Form wizard JavaScript
    ├── validation.js           # Client-side validation
    └── style.css               # Form styling
```

## MVP Scope

- **Session-based storage** (no database required)
- **Local file uploads** (for profile pictures/documents)
- **Built-in validation** (no external validation libraries)
- **Simple UI** (clean CSS, no frameworks)
- **Demo data only** (form submissions aren't persisted permanently)

## Form Steps Detail

### Step 1: Personal Information
- First Name, Last Name (required)
- Email (required, validated format)
- Phone Number (optional, format validation)

### Step 2: Address Information
- Street Address (required)
- City, State, ZIP (required)
- Country (dropdown selection)

### Step 3: File Uploads
- Profile Picture (optional, image files only)
- Resume/CV (optional, PDF or DOC)
- Additional Documents (optional, multiple files)

### Step 4: Preferences
- Newsletter subscription (checkbox)
- Preferred contact method (radio buttons)
- Interests (multiple checkboxes)
- Comments (textarea)

### Step 5: Review & Submit
- Summary of all entered data
- File upload confirmations
- Edit links to go back to specific steps
- Final submit button

## Demo Features

- **Progress Bar**: Visual indication of wizard completion
- **Form Persistence**: Data saved between steps
- **Validation**: Real-time and server-side validation
- **File Handling**: Upload and preview capabilities
- **Mobile Responsive**: Works on all device sizes
- **Accessibility**: Proper form labels and ARIA attributes

This MVP demonstrates Serv's comprehensive form handling capabilities! 