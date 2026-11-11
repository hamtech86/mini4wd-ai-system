#include <assert.h>
#include <stdint.h>
#include "../../firmware/motor/ProtocolV2AdcScheduler.h"
using namespace mini4wd310;
static void take(AdcCadenceScheduler& s,uint32_t now,uint8_t ch,bool missing){
  uint8_t got=255; uint32_t scheduled=0; bool lost=false;
  assert(s.take_due(now,&got,&scheduled,&lost)); assert(got==ch); assert(lost==missing);
}
static void test_scan_order_and_25_75ms_cycle(){
  AdcCadenceScheduler s; const uint8_t order[6]={0,1,4,5,2,3};
  s.start(1000);
  for(uint8_t i=0;i<6;++i) take(s,1000,order[i],false);
  uint8_t c=0; uint32_t t=0; bool m=false;
  assert(!s.take_due(25999,&c,&t,&m));
  for(uint8_t i=0;i<6;++i) take(s,26000,order[i],false);
  assert(!s.take_due(100999,&c,&t,&m));
  for(uint8_t i=0;i<6;++i) take(s,101000,order[i],false);
}
static void test_overrun_becomes_not_acquired_slots(){
  AdcCadenceScheduler s; s.start(0); take(s,0,0,false);
  const uint8_t missed[5]={1,4,5,2,3};
  for(uint8_t i=0;i<5;++i) take(s,25000,missed[i],true);
  const uint8_t second[6]={0,1,4,5,2,3};
  for(uint8_t i=0;i<6;++i) take(s,25000,second[i],false);
  uint8_t c=0; uint32_t t=0; bool m=false;
  assert(!s.take_due(99999,&c,&t,&m));
  take(s,100000,0,false);
}
static void test_micros_wrap(){
  AdcCadenceScheduler s; const uint32_t start=UINT32_MAX-10000UL;
  const uint8_t order[6]={0,1,4,5,2,3}; s.start(start);
  for(uint8_t i=0;i<6;++i) take(s,start,order[i],false);
  const uint32_t second=start+static_cast<uint32_t>(25000);
  for(uint8_t i=0;i<6;++i) take(s,second,order[i],false);
}
static void test_stop_and_restart(){
  AdcCadenceScheduler s; s.start(100); take(s,100,0,false); s.stop();
  uint8_t c=0; uint32_t t=0; bool m=false;
  assert(!s.take_due(1000000,&c,&t,&m));
  s.start(2000000); take(s,2000000,0,false);
}
int main(){
 test_scan_order_and_25_75ms_cycle(); test_overrun_becomes_not_acquired_slots();
 test_micros_wrap(); test_stop_and_restart(); return 0;
}
