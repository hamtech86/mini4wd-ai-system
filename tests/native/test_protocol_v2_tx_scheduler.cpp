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

static void test_large_adc_batch_is_built_directly_in_tx_workspace(){
  ProtocolV2TxScheduler tx; FakeSerial s(64);
  const uint8_t session[16]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16};
  const uint32_t epoch=epoch_tag_for_boot_id(9);
  assert(tx.begin_adc_batch(100,3));
  assert(tx.batch_building() && tx.busy());
  for(uint8_t i=0;i<12;++i)
    assert(tx.append_adc_sample(1000U+i*100U,(uint8_t)(i%6),500,
                                static_cast<uint16_t>(i/6+1),0,0));
  assert(tx.finish_adc_batch(session,epoch));
  assert(!tx.batch_building() && tx.busy());
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
  uint8_t encoded[kMaxV2WireSize]={0}; uint16_t encoded_length=0;
  memcpy(encoded+1+kHeaderSize,payload,kAdcBatchPayloadSize);
  assert(encode_frame_in_place(ADC_BATCH,session,epoch,0,encoded,
                               kAdcBatchPayloadSize,sizeof(encoded),&encoded_length));
  drain(tx,s);
  assert(s.bytes==std::vector<uint8_t>(encoded,encoded+encoded_length));
}

static void test_adc_batch_preserves_failed_attempt_status_slots(){
  ProtocolV2TxScheduler tx; FakeSerial s(64);
  const uint8_t session[16]={1,3,5,7,9,11,13,15,2,4,6,8,10,12,14,16};
  const uint32_t epoch=epoch_tag_for_boot_id(19);
  assert(tx.begin_adc_batch(500,7));
  for(uint8_t i=0;i<12;++i){
    const uint8_t status = (i % 4 == 0) ? ADC_ACQ_OK :
      (i % 4 == 1) ? ADC_PRECONDITION_INVALID :
      (i % 4 == 2) ? ADC_CONVERSION_TIMEOUT : ADC_NOT_ACQUIRED;
    const uint16_t raw = status == ADC_ACQ_OK ? 0 : 0xFFFF;
    assert(tx.append_adc_sample(5000U+i*100U,(uint8_t)(i%6),raw,
                                static_cast<uint16_t>(i/6+1),status,0));
  }
  assert(tx.finish_adc_batch(session,epoch));
  drain(tx,s);
  FrameView decoded;
  assert(decode_frame_in_place(s.bytes.data(),static_cast<uint16_t>(s.bytes.size()-1),&decoded));
  assert(decoded.message_type==ADC_BATCH && decoded.payload[9]==12);
  for(uint8_t i=0;i<12;++i){
    const uint8_t* sample=decoded.payload+11+(uint16_t)i*12;
    const uint8_t expected_status = (i % 4 == 0) ? ADC_ACQ_OK :
      (i % 4 == 1) ? ADC_PRECONDITION_INVALID :
      (i % 4 == 2) ? ADC_CONVERSION_TIMEOUT : ADC_NOT_ACQUIRED;
    assert(sample[9]==expected_status);
    assert(read_u16(sample+5)==(expected_status==ADC_ACQ_OK?0:0xFFFF));
  }
}

static void test_stop_ack_preempts_adc_batch_workspace(){
  ProtocolV2TxScheduler tx; FakeSerial s(64);
  DeviceReplyV2 stop; memset(&stop,0,sizeof(stop));
  stop.valid=true; stop.message_type=STOP_ACK; stop.session_uuid[0]=1;
  stop.epoch_tag=epoch_tag_for_boot_id(9); stop.command_id=3;
  stop.payload_length=3; stop.payload[0]=0; stop.payload[1]=0; stop.payload[2]=2;
  assert(tx.begin_adc_batch(200,0));
  assert(tx.append_adc_sample(2000,0,512,1,0,0));
  assert(tx.enqueue(stop));
  assert(tx.batch_building());
  tx.service(s); // Drops unfinished batch and sends STOP_ACK first.
  assert(!tx.batch_building());
  const std::vector<uint8_t> expected_stop=expected(stop);
  drain(tx,s);
  assert(s.bytes==expected_stop);
}

int main(){
  test_large_adc_batch_is_built_directly_in_tx_workspace();
  test_adc_batch_preserves_failed_attempt_status_slots();
  test_stop_ack_preempts_adc_batch_workspace();
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
