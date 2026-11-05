#include <assert.h>
#include <stdint.h>
#include <string.h>
#include <vector>
#include "../../firmware/motor/ProtocolV2TxScheduler.h"
using namespace mini4wd310;
struct FakeSerial {
  int capacity; std::vector<uint8_t> bytes; std::vector<size_t> chunks;
  explicit FakeSerial(int c):capacity(c){}
  int availableForWrite() const { return capacity; }
  size_t write(const uint8_t* p,size_t n){chunks.push_back(n);bytes.insert(bytes.end(),p,p+n);return n;}
};
static std::vector<uint8_t> expected(const DeviceReplyV2& r){
  uint8_t b[kMaxV2WireSize]={0}; memcpy(b+1+kHeaderSize,r.payload,r.payload_length);
  uint16_t n=0; assert(encode_frame_in_place(r.message_type,r.session_uuid,r.epoch_tag,r.command_id,b,r.payload_length,sizeof(b),&n));
  return std::vector<uint8_t>(b,b+n);
}
static void drain(ProtocolV2TxScheduler& tx,FakeSerial& s){
  for(int i=0;i<100 && tx.busy();++i) tx.service(s);
  assert(!tx.busy());
}

static void test_large_adc_batch_uses_tx_workspace_without_pending_copy(){
  ProtocolV2TxScheduler tx; FakeSerial s(64);
  const uint8_t session[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  uint8_t payload[kAdcBatchPayloadSize]={0};
  write_u64(payload,100); payload[8]=0; payload[9]=12; payload[10]=3;
  for(uint8_t i=0;i<12;++i){
    uint8_t* sample=payload+11+(uint16_t)i*12;
    write_u32(sample,1000U+i*100U);
    sample[4]=(uint8_t)(i%6);
    write_u16(sample+5,500);
    write_u16(sample+7,static_cast<uint16_t>(i/6+1));
    sample[9]=0; write_u16(sample+10,0);
  }
  assert(tx.enqueue_frame(ADC_BATCH,session,epoch_tag_for_boot_id(9),0,
                          payload,kAdcBatchPayloadSize));
  assert(tx.busy());
  assert(!tx.enqueue_frame(ADC_BATCH,session,epoch_tag_for_boot_id(9),0,
                           payload,kAdcBatchPayloadSize));
  uint8_t encoded[kMaxV2WireSize]={0}; uint16_t encoded_length=0;
  memcpy(encoded+1+kHeaderSize,payload,kAdcBatchPayloadSize);
  assert(encode_frame_in_place(ADC_BATCH,session,epoch_tag_for_boot_id(9),0,
                               encoded,kAdcBatchPayloadSize,sizeof(encoded),&encoded_length));
  drain(tx,s);
  assert(s.bytes==std::vector<uint8_t>(encoded,encoded+encoded_length));
}
\nint main(){
  ProtocolV2TxScheduler tx; FakeSerial s(5);
  DeviceReplyV2 first; memset(&first,0,sizeof(first));
  first.valid=true; first.message_type=ERROR_MSG; first.command_id=0;
  first.payload_length=8; first.payload[0]=1; first.payload[1]=PWM_SET; write_u32(first.payload+4,1);
  assert(tx.enqueue(first)); tx.service(s); assert(s.bytes.size()==5 && tx.busy());
  DeviceReplyV2 low=first; low.payload[0]=2; assert(tx.enqueue(low));
  DeviceReplyV2 stop; memset(&stop,0,sizeof(stop));
  stop.valid=true; stop.message_type=STOP_ACK; stop.session_uuid[0]=1;
  stop.epoch_tag=1; stop.command_id=3; stop.payload_length=3;
  stop.payload[0]=0; stop.payload[1]=0; stop.payload[2]=2;
  assert(tx.enqueue(stop));
  const std::vector<uint8_t> a=expected(first), b=expected(stop);
  s.capacity=64; drain(tx,s);
  std::vector<uint8_t> joined=a; joined.insert(joined.end(),b.begin(),b.end());
  assert(s.bytes==joined);
  for(size_t i=0;i<s.chunks.size();++i) assert(s.chunks[i]<=16);
  return 0;
}
