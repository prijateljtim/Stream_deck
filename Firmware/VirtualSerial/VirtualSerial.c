#include "VirtualSerial.h"
#include <util/delay.h>
#include <stdio.h>
#include <avr/wdt.h>
#include <avr/power.h>
#include <string.h>
#include <avr/interrupt.h>

// 1. OBVEZNA LUFA STRUKTURA
USB_ClassInfo_CDC_Device_t VirtualSerial_CDC_Interface =
    {
        .Config =
            {
                .ControlInterfaceNumber   = INTERFACE_ID_CDC_CCI,
                .DataINEndpoint           =
                    {
                        .Address          = CDC_TX_EPADDR,
                        .Size             = CDC_TXRX_EPSIZE,
                        .Banks            = 1,
                    },
                .DataOUTEndpoint          =
                    {
                        .Address          = CDC_RX_EPADDR,
                        .Size             = CDC_TXRX_EPSIZE,
                        .Banks            = 1,
                    },
                .NotificationEndpoint     =
                    {
                        .Address          = CDC_NOTIFICATION_EPADDR,
                        .Size             = CDC_NOTIFICATION_EPSIZE,
                        .Banks            = 1,
                    },
            },
    };

int USB_PosljiCrko(char c, FILE *stream) {
    if (c == '\n') {
        CDC_Device_SendByte(&VirtualSerial_CDC_Interface, '\r');
    }
    CDC_Device_SendByte(&VirtualSerial_CDC_Interface, c);
    return 0;
}
FILE usb_stream = FDEV_SETUP_STREAM(USB_PosljiCrko, NULL, _FDEV_SETUP_WRITE);

char vhodni_buffer[64]; 
uint8_t buffer_index = 0;

// Tuki preberemo če nam je kej poslal aplikacija za connection
void con(void){

    int16_t prejeti_znak = CDC_Device_ReceiveByte(&VirtualSerial_CDC_Interface);
        
    if (prejeti_znak >= 0) 
    {
        uint8_t bajt = (uint8_t)prejeti_znak;

        if (bajt == 0xAA) 
        {
            CDC_Device_SendByte(&VirtualSerial_CDC_Interface, 0xAB); //Se oglasi da je živ
            CDC_Device_SendByte(&VirtualSerial_CDC_Interface, 0xAC); //Pove da je strem deck, mogoče v prihodnisti da bi bilo še več naprav
        }

    }
}


typedef struct {
    volatile uint8_t *pin_register; 
    uint8_t pin_bit;               
    uint8_t last_state;            
    uint8_t name;                 
    uint8_t debounce_counter; 
} Gumb_t;

Gumb_t moji_gumbi[] = {
    {&PIND, PORTD4, 1, 0x01, 0}, //Tipka 1  
    {&PIND, PORTD6, 1, 0x04, 0}, //Tipka 4  
    {&PIND, PORTD7, 1, 0x02, 0}, //Tipka 2
    {&PINB, PORTB4, 1, 0x05, 0}, //Tipka 5
    {&PINB, PORTB5, 1, 0x03, 0}, //Tipka 3
    {&PINB, PORTB6, 1, 0x06, 0}, //Tipka 6
    {&PINC, PORTC6, 1, 0x07, 0}  //Tipka Mute 
};

typedef struct {
    volatile uint8_t *pin_register; 
    uint8_t pin_bit;               
    uint8_t last_state; 
    uint8_t position;           
    uint8_t name;                 
    uint8_t debounce_counter; 
} Encoder_t;

Encoder_t encoder[] = {
    {&PIND, PORTD0, 1, 1, 0x11, 0}, //Encoder pin A
    {&PIND, PORTD1, 1, 1, 0x12, 0}  //Encoder pin B
};

#define STEVILO_GUMBOV (sizeof(moji_gumbi) / sizeof(Gumb_t))

void check_button_press(void) {
    for (uint8_t j = 0; j < STEVILO_GUMBOV; j++) {
        uint8_t current_state = ((*moji_gumbi[j].pin_register) & (1 << moji_gumbi[j].pin_bit)) ? 1 : 0;
        if (current_state != moji_gumbi[j].last_state) {
            moji_gumbi[j].debounce_counter++;
            if (moji_gumbi[j].debounce_counter >= 150) {
                if (current_state == 0) { 
                    CDC_Device_SendByte(&VirtualSerial_CDC_Interface, moji_gumbi[j].name);
                }
                moji_gumbi[j].last_state = current_state;
                moji_gumbi[j].debounce_counter = 0;
            }
        } else {
            moji_gumbi[j].debounce_counter = 0;
        }
    }
}

// Encoder upam da to zdej dela
volatile int32_t stevec = 0;   
int32_t zadnji_stevec = 0;
volatile uint8_t staro_stanje_pinov = 0; // Tu čip hrani prejšnjo sliko pinov

//Sveti jožef in sveta marija
static const int8_t tabela_premik[] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

ISR(INT0_vect) {
    uint8_t trenutno_stanje = 0;
    if (PIND & (1 << PIND0)) trenutno_stanje |= 2; 
    if (PIND & (1 << PIND1)) trenutno_stanje |= 1; 
    
    uint8_t index = (staro_stanje_pinov << 2) | trenutno_stanje;
    staro_stanje_pinov = trenutno_stanje;
    
    stevec += tabela_premik[index & 0x0F];
}

ISR(INT1_vect) {
    uint8_t trenutno_stanje = 0;
    if (PIND & (1 << PIND0)) trenutno_stanje |= 2;
    if (PIND & (1 << PIND1)) trenutno_stanje |= 1;
    
    uint8_t index = (staro_stanje_pinov << 2) | trenutno_stanje;
    staro_stanje_pinov = trenutno_stanje;
    
    stevec += tabela_premik[index & 0x0F];
}


void SetupHardware(void)
{
    MCUSR &= ~(1 << WDRF);
    wdt_disable();
    
    // Omogičimo interupte
    EIMSK = (1 << INT0) | (1 << INT1); 
    
    // Na kaj se proži (na raise in falling edge)
    EICRA = (0 << ISC11) | (1 << ISC10) | (0 << ISC01) | (1 << ISC00); 
    
    //Dfiniramo pine kot vhodne in da so pull upi
    PORTB = (1<<PB4)|(1<<PB5)|(1<<PB6);
    PORTC = (1<<PC6);
    PORTD = (1<<PD0)|(1<<PD1)|(1<<PD4)|(1<<PD6)|(1<<PD7);
    
    DDRB = (0<<PB4)|(0<<PB5)|(0<<PB6);
    DDRC = (0<<PC6);
    DDRD = (0<<PD0)|(0<<PD1)|(0<<PD4)|(0<<PD6)|(0<<PD7);
    
    clock_prescale_set(clock_div_1);
    USB_Init();
}


int main(void)
{
    SetupHardware(); 
    GlobalInterruptEnable();

    stdout = &usb_stream;

    uint16_t encoder_cooldown = 0;

    for (;;)
    {
        con();
        check_button_press();

        if (encoder_cooldown > 0) {
            encoder_cooldown--;
        }

        int32_t trenutni_stevec = stevec;
        int32_t razlika = trenutni_stevec - zadnji_stevec;

        if (encoder_cooldown == 0) {
            
            if (razlika >= 2) {
                CDC_Device_SendByte(&VirtualSerial_CDC_Interface, encoder[0].name); // Naprej
                zadnji_stevec = trenutni_stevec;
                encoder_cooldown = 1000;         
            } 
            else if (razlika <= -2) {
                CDC_Device_SendByte(&VirtualSerial_CDC_Interface, encoder[1].name); //Nazaj
                zadnji_stevec = trenutni_stevec;
                encoder_cooldown = 1000;         
            }
        }

        CDC_Device_USBTask(&VirtualSerial_CDC_Interface);
        USB_USBTask();
    }
}


void EVENT_USB_Device_ConfigurationChanged(void)
{
    CDC_Device_ConfigureEndpoints(&VirtualSerial_CDC_Interface);
}

void EVENT_USB_Device_ControlRequest(void)
{
    CDC_Device_ProcessControlRequest(&VirtualSerial_CDC_Interface);
}